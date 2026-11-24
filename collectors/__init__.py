"""Market data collectors, one sub-package per platform."""
from __future__ import annotations

import gzip
import json
import logging
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from sqlite3 import Connection

# A plain client name: Clore.ai answers Python's default user agent with 403 (2026-11-24). It names
# no project or person, and imitates no browser.
USER_AGENT = "gpu-market-collector/0.1"
RETRY_STATUS = {429, 502, 503, 504}
FEED_INTERVAL_S = 2.0
IPV4 = re.compile(rb"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")

log = logging.getLogger("collectors")


class _JsonLines(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="seconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            **getattr(record, "data", {}),
        }
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def setup_logging(level: int = logging.INFO) -> None:
    """Structured logs: one JSON object per line on stderr. Pass fields with extra={"data": {...}}."""
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonLines())
    logging.basicConfig(level=level, handlers=[handler], force=True)


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_bytes(url: str, *, timeout: float = 60, attempts: int = 4, backoff_s: float = 2.0,
              sleep: Callable[[float], None] = time.sleep) -> bytes:
    """GET a URL. Retries 429/5xx and network errors with exponential backoff."""
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as e:
            if e.code not in RETRY_STATUS or attempt == attempts:
                raise
        except OSError:  # connection errors and timeouts
            if attempt == attempts:
                raise
        delay = backoff_s * 2 ** (attempt - 1)
        log.warning("request failed, retrying", extra={"data": {"url": url, "attempt": attempt, "delay_s": delay}})
        sleep(delay)
    raise AssertionError("unreachable")


def collect_feeds(con: Connection, platform: str, feeds: dict[str, tuple[str, Callable[[object], bool]]],
                  sleep: Callable[[float], None] = time.sleep) -> int:
    """Download each public feed once and store the body as served, if it has the expected shape and
    holds nothing that looks like an IP address. Returns the number of feeds that failed."""
    run_id = _now()
    with con:
        con.execute("INSERT INTO market_runs (platform, run_id, planned) VALUES (?, ?, ?)", (platform, run_id, len(feeds)))
    failed = 0
    for i, (feed, (url, valid)) in enumerate(feeds.items()):
        if i:
            sleep(FEED_INTERVAL_S)
        ctx = {"run_id": run_id, "platform": platform, "feed": feed}
        try:
            body = get_bytes(url, sleep=sleep)
            if not valid(json.loads(body)):
                raise ValueError("unexpected feed shape")
            if IPV4.search(body):  # the project never stores host IP addresses
                raise ValueError("feed contains IP-address-like text")
            with con:
                con.execute("INSERT INTO market_feeds (platform, feed, run_id, collected_at, url, raw_gzip)"
                            " VALUES (?, ?, ?, ?, ?, ?)", (platform, feed, run_id, _now(), url, gzip.compress(body)))
        except Exception:  # one bad feed must not lose the others
            log.exception("feed failed", extra={"data": ctx})
            failed += 1
            continue
        log.info("feed saved", extra={"data": {**ctx, "bytes": len(body)}})
    return failed
