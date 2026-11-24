"""Public feed collection and report §10. All feed contents here are SIMULATED."""
import gzip
import json

import collectors
from analytics.market_report import build
from database import connect

RUN = "2026-11-23T10:00:00Z"
CLORE = {"status": "ok", "all_servers": [
    {"id": 1, "owner": 9, "rented": True, "gpu_array": ["RTX 3060"],
     "specs": {"gpuram": 12, "net": {"cc": "CN"}}, "price": {"usd": {"on_demand_usd": 1.2}}},
    {"id": 2, "owner": 9, "rented": False, "gpu_array": ["RTX 3060", "RTX 3060"],
     "specs": {"gpuram": 12, "net": {"cc": "US"}}, "price": {"usd": {"on_demand_usd": 2.88}}},
    {"id": 3, "owner": 8, "rented": False, "gpu_array": ["RTX 3060"],
     "specs": {"gpuram": 8, "net": {"cc": "US"}}, "price": {"usd": {}}},  # 8 GB variant, no USD price
    {"id": 4, "owner": 7, "rented": True, "gpu_array": ["RTX 3060", "RTX 3070"],  # mixed: left out
     "specs": {"gpuram": 8, "net": {"cc": "US"}}, "price": {"usd": {"on_demand_usd": 2.0}}},
]}
SALAD_RATES = {"updatedAt": "2026-11-23T08:00:00Z", "window": {"from": "2026-11-16", "to": "2026-11-22", "daysWithData": 7},
               "classes": [{"id": "rtx-3060", "name": "RTX 3060", "mean": 0.0331, "p25": 0.0248, "p75": 0.0393, "work": 90}]}
SALAD_DEMAND = [{"name": "NVIDIA GeForce RTX 3060", "demandTier": "high", "utilizationPct": 94}]


def test_collect_feeds_stores_bodies_and_counts_failures(monkeypatch):
    bodies = {"u1": json.dumps(CLORE).encode(), "u2": b"<html>not json</html>"}
    monkeypatch.setattr(collectors, "get_bytes", lambda url, sleep: bodies[url])
    con = connect(":memory:")
    assert collectors.collect_feeds(con, "clore", {"servers": "u1", "broken": "u2"}, sleep=lambda s: None) == 1
    (raw,) = con.execute("SELECT raw_gzip FROM market_feeds").fetchone()
    assert gzip.decompress(raw) == bodies["u1"]  # stored as served
    assert con.execute("SELECT planned FROM market_runs WHERE platform = 'clore'").fetchone()[0] == 2


def test_report_section_from_feeds():
    con = connect(":memory:")
    con.execute("INSERT INTO market_runs (platform, run_id, planned) VALUES ('vast', ?, 16)", (RUN,))
    for platform, feed, body in (("clore", "servers", CLORE), ("salad", "earning-rates", SALAD_RATES),
                                 ("salad", "demand-monitor", SALAD_DEMAND)):
        con.execute("INSERT INTO market_feeds (platform, feed, run_id, collected_at, url, raw_gzip, data_class)"
                    " VALUES (?, ?, ?, ?, 'u', ?, 'simulated')", (platform, feed, RUN, RUN, gzip.compress(json.dumps(body).encode())))
    report = build(con, "2026-11-23")
    assert report.startswith("# SIMULATED")  # simulated feeds mark the report too
    assert "Servers that mix GPU models are left out (1 in the last download)" in report
    # 3 GPUs of 12 GB, 1 on a rented server; the CN one is rented; prices 0.05 and 0.06 per GPU-hour
    assert "| RTX 3060 12GB | 3 | 33% | 1 | 100% | $0.055 | $0.050 |" in report
    assert "| RTX 3060 8GB | 1 | 0% | 0 | — | — | — |" in report
    assert "| RTX 3060 | $0.033 | $0.025–$0.039 | 90% | high | 94 |" in report
