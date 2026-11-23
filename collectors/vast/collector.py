"""Vast.ai market collector.

One run sends one search request per slice (GPU model x scope x `rentable` filter) and stores each
response as a snapshot: the raw response (gzip, private fields removed) and one normalised row per
offer. Endpoint and request shape are those of the official `vastai search offers` (CLI 1.11.2).

    python -m collectors.vast.collector        env: GPU_NODE_DB, VAST_API_KEY (optional)

Platform behaviour this design rests on (measured 2026-11-23, docs/platform-research.md):
- a response is a varying sample of the matching offers, so one snapshot is a lower bound of supply;
  analytics take the union of a day's hourly snapshots;
- an unauthenticated response holds at most 64 offers;
- searches count against a daily quota (HTTP 429 'search_quota_exceeded', reset 00:00 UTC).
"""
from __future__ import annotations

import gzip
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from sqlite3 import Connection

from collectors import setup_logging
from database import connect

URL = "https://console.vast.ai/api/v0/bundles/"
GPUS = ("RTX 3060", "RTX 3090", "RTX 4090", "RTX 5090")
SCOPES: dict[str, list[str] | None] = {
    "GLOBAL": None,
    "CN": ["CN"],  # mainland China; the platform codes HK, MO and TW separately
    "NEARBY": ["HK", "MO", "TW", "JP", "KR", "SG", "VN", "TH", "MY"],
}
# (scope, rentable filter). Non-rentable listings only for CN: 16 requests per run keeps an hourly
# schedule at 384 searches a day.
SLICES = (("GLOBAL", True), ("CN", True), ("CN", False), ("NEARBY", True))
LIMIT = 64  # largest response seen without an API key
REQUEST_INTERVAL_S = 2.0
RETRY_STATUS = {429, 502, 503, 504}  # same set as the official client
PRIVATE_FIELDS = ("public_ipaddr", "hostname", "webpage", "geolocode")  # never stored

log = logging.getLogger("collectors.vast")


class QuotaExceeded(Exception):
    """Daily search quota used up: every further request fails until 00:00 UTC."""


def post_json(url: str, body: dict, headers: dict[str, str], *, timeout: float = 60, attempts: int = 4,
              backoff_s: float = 2.0, sleep: Callable[[float], None] = time.sleep) -> dict:
    """POST JSON, return the decoded reply. Retries 429/5xx and network errors with exponential backoff."""
    data = json.dumps(body).encode()
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as e:
            if e.code == 429 and b"search_quota_exceeded" in e.read():
                raise QuotaExceeded from e
            if e.code not in RETRY_STATUS or attempt == attempts:
                raise
        except OSError:  # connection errors and timeouts
            if attempt == attempts:
                raise
        delay = backoff_s * 2 ** (attempt - 1)
        log.warning("request failed, retrying", extra={"data": {"attempt": attempt, "delay_s": delay}})
        sleep(delay)
    raise AssertionError("unreachable")


def request_body(gpu: str, scope: str, rentable: bool) -> dict:
    body = {"gpu_name": {"eq": gpu}, "rentable": {"eq": rentable}, "cpu_arch": {"in": ["amd64", "arm64"]},
            "type": "on-demand", "limit": LIMIT}
    if SCOPES[scope]:
        body["geolocation"] = {"in": SCOPES[scope]}
    return body


def _str(value: object) -> str | None:
    return None if value is None else str(value)


def normalize(offer: dict) -> dict:
    """Map one Vast offer to a market_offers row (without snapshot_id)."""
    region, _, country = (offer.get("geolocation") or "").rpartition(", ")
    frac = offer.get("gpu_frac")
    duration = offer.get("duration")  # seconds until the host's listing end date
    return {
        "offer_id": str(offer["id"]),
        "machine_id": _str(offer.get("machine_id")),
        "host_id": _str(offer.get("host_id")),
        "gpu_name": offer["gpu_name"],
        "num_gpus": offer["num_gpus"],
        "machine_gpus": round(offer["num_gpus"] / frac) if frac else None,
        "gpu_ram_mb": offer.get("gpu_ram"),
        "country": country or None,
        "region": region or None,
        "verification": offer.get("verification"),
        "reliability": offer.get("reliability"),
        "cpu_name": offer.get("cpu_name"),
        "cpu_cores": offer.get("cpu_cores_effective"),
        "ram_mb": offer.get("cpu_ram"),
        "disk_gb": offer.get("disk_space"),
        "inet_up_mbps": offer.get("inet_up"),
        "inet_down_mbps": offer.get("inet_down"),
        "open_ports": offer.get("direct_port_count"),
        "price_type": "on-demand",
        "price_usd_hr": offer["dph_base"],
        "total_usd_hr": offer.get("dph_total"),
        "min_bid_usd_hr": offer.get("min_bid"),
        "rentable": offer.get("rentable"),
        "max_duration_days": None if duration is None else duration / 86400,
        "gpu_power_limit_w": offer.get("gpu_max_power"),
    }


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def save(con: Connection, *, run_id: str, gpu: str, scope: str, rentable: bool, auth: str, body: dict,
         response: dict, data_class: str = "collected") -> int:
    """Store one response as a snapshot in a single transaction; returns the snapshot id."""
    offers = response["offers"]
    for offer in offers:
        for key in PRIVATE_FIELDS:
            offer.pop(key, None)
    rows = [normalize(o) for o in offers]
    with con:
        snapshot_id = con.execute(
            "INSERT INTO market_snapshots (platform, run_id, collected_at, gpu_name, scope, rentable, auth,"
            " request, offer_count, raw_gzip, data_class) VALUES ('vast', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (run_id, _now(), gpu, scope, rentable, auth, json.dumps(body), len(offers),
             gzip.compress(json.dumps(response).encode()), data_class),
        ).lastrowid
        if rows:
            cols = ["snapshot_id", *rows[0]]
            con.executemany(
                f"INSERT INTO market_offers ({', '.join(cols)}) VALUES ({', '.join(':' + c for c in cols)})",
                [{"snapshot_id": snapshot_id, **row} for row in rows],
            )
    return snapshot_id


def run(con: Connection, api_key: str | None = None, sleep: Callable[[float], None] = time.sleep) -> int:
    """Collect every slice once. Returns the number of slices that produced no snapshot."""
    run_id = _now()
    auth = "api_key" if api_key else "anonymous"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    plan = [(gpu, scope, rentable) for gpu in GPUS for scope, rentable in SLICES]
    with con:
        con.execute("INSERT INTO market_runs (platform, run_id, planned) VALUES ('vast', ?, ?)", (run_id, len(plan)))
    failed = 0
    for i, (gpu, scope, rentable) in enumerate(plan):
        if i:
            sleep(REQUEST_INTERVAL_S)
        body = request_body(gpu, scope, rentable)
        ctx = {"run_id": run_id, "gpu": gpu, "scope": scope, "rentable": rentable}
        try:
            response = post_json(URL, body, headers, sleep=sleep)
            snapshot_id = save(con, run_id=run_id, gpu=gpu, scope=scope, rentable=rentable, auth=auth,
                               body=body, response=response)
        except QuotaExceeded:
            log.error("daily search quota exceeded, stopping run", extra={"data": ctx})
            failed += len(plan) - i
            break
        except Exception:  # one bad slice must not lose the rest of the run
            log.exception("slice failed", extra={"data": ctx})
            failed += 1
            continue
        log.info("snapshot saved", extra={"data": {**ctx, "snapshot_id": snapshot_id,
                                                   "offers": len(response["offers"])}})
    log.info("run finished", extra={"data": {"run_id": run_id, "slices": len(plan), "failed": failed}})
    return failed


def main() -> int:
    setup_logging()
    # strip: a CR or newline from an edited .env makes an invalid header whose error text holds the key
    return 1 if run(connect(), os.environ.get("VAST_API_KEY", "").strip() or None) else 0


if __name__ == "__main__":
    sys.exit(main())
