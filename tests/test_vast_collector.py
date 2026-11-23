import gzip
import io
import urllib.error
import urllib.request

import pytest

from analytics.market_report import build
from collectors.vast import collector
from database import connect

DAY = "2026-11-23T00:00:00Z"


def test_normalize(offer):
    row = collector.normalize(offer)
    assert (row["country"], row["region"]) == ("CN", "Guangdong")
    assert row["machine_gpus"] == 8  # 2 GPUs are a quarter of the machine
    assert row["max_duration_days"] == 10
    assert (row["price_usd_hr"], row["host_id"]) == (0.8, "9")
    assert collector.normalize({**offer, "geolocation": None})["country"] is None


def test_request_body_scopes():
    assert "geolocation" not in collector.request_body("RTX 3090", "GLOBAL", True)
    assert collector.request_body("RTX 3090", "CN", False)["geolocation"] == {"in": ["CN"]}


def test_save_drops_private_fields(offer):
    con = connect(":memory:")
    sid = collector.save(con, run_id=DAY, gpu="RTX 4090", scope="CN", rentable=True, auth="anonymous",
                         body={}, response={"offers": [offer]}, data_class="simulated")
    raw = gzip.decompress(con.execute("SELECT raw_gzip FROM market_snapshots WHERE id = ?", (sid,)).fetchone()[0])
    assert b"203.0.113.7" not in raw and b"host.example" not in raw and b"geolocode" not in raw
    assert con.execute("SELECT machine_gpus FROM market_offers").fetchone()[0] == 8


def test_run_survives_a_failed_slice_and_stops_on_quota(monkeypatch, offer):
    calls = []

    def fake_post(url, body, headers, sleep):
        calls.append(body)
        if len(calls) == 2:
            raise urllib.error.URLError("connection reset")
        if len(calls) == 4:
            raise collector.QuotaExceeded
        return {"offers": [{**offer, "id": len(calls)}]}

    monkeypatch.setattr(collector, "post_json", fake_post)
    con = connect(":memory:")
    failed = collector.run(con, sleep=lambda s: None)
    planned = len(collector.GPUS) * len(collector.SLICES)
    assert len(calls) == 4  # nothing sent after the quota error
    assert failed == 1 + (planned - 3)
    assert con.execute("SELECT COUNT(*) FROM market_snapshots").fetchone()[0] == 2
    assert con.execute("SELECT planned FROM market_runs").fetchone()[0] == planned


def test_run_that_stored_nothing_still_counts_as_missing(monkeypatch):
    def quota(url, body, headers, sleep):
        raise collector.QuotaExceeded

    monkeypatch.setattr(collector, "post_json", quota)
    con = connect(":memory:")
    collector.run(con, sleep=lambda s: None)
    day = con.execute("SELECT substr(run_id, 1, 10) FROM market_runs").fetchone()[0]
    assert "| Searches missing on this day | 16 of 16 |" in build(con, day)


def test_post_json_retries_transient_errors_not_quota(monkeypatch):
    replies = [urllib.error.HTTPError(collector.URL, 503, "busy", {}, io.BytesIO(b"")), io.BytesIO(b'{"offers": []}')]

    def fake_urlopen(request, timeout):
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    sleeps = []
    assert collector.post_json(collector.URL, {}, {}, sleep=sleeps.append) == {"offers": []}
    assert sleeps == [2.0]
    replies.append(urllib.error.HTTPError(collector.URL, 429, "quota", {},
                                          io.BytesIO(b'{"error": "search_quota_exceeded"}')))
    with pytest.raises(collector.QuotaExceeded):
        collector.post_json(collector.URL, {}, {}, sleep=sleeps.append)
    assert sleeps == [2.0]  # the quota error was not retried
