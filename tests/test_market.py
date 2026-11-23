import sqlite3

import pytest

from analytics.market_report import build
from analytics.pricing import machines_seen, p10_p50_p90
from collectors.vast.collector import save
from database import connect


def test_percentiles():
    assert p10_p50_p90([]) is None
    assert p10_p50_p90([2.0]) == (2.0, 2.0, 2.0)
    assert p10_p50_p90([float(v) for v in range(1, 12)]) == (2.0, 6.0, 10.0)


def test_machines_counted_once_at_lowest_gpu_price_and_report_marked_simulated(offer):
    con = connect(":memory:")
    con.execute("INSERT INTO market_runs (platform, run_id, planned) VALUES ('vast', '2026-11-23T10:00:00Z', 16)")
    offers = [  # machine 7 in two sizes, machine 8 with ECC on, machine 9 a 48 GB board
        {**offer, "id": 1, "num_gpus": 1, "gpu_frac": 0.5, "dph_base": 0.40},
        {**offer, "id": 2, "num_gpus": 2, "gpu_frac": 1.0, "dph_base": 0.70, "verification": "unverified"},
        {**offer, "id": 3, "machine_id": 8, "num_gpus": 1, "gpu_frac": 1.0, "dph_base": 0.50, "gpu_ram": 23028},
        {**offer, "id": 4, "machine_id": 9, "num_gpus": 1, "gpu_frac": 1.0, "dph_base": 0.60, "gpu_ram": 49140},
    ]
    save(con, run_id="2026-11-23T10:00:00Z", gpu="RTX 4090", scope="CN", rentable=True, auth="anonymous",
         body={}, response={"offers": offers}, data_class="simulated")
    rows = machines_seen(con, "2026-11-23")
    # machine 7's price and verification come from the same (cheapest) observation
    assert {(r["machine_id"], r["vram_gb"], round(r["gpu_price"], 3), r["gpus"], r["verification"]) for r in rows} == {
        ("7", 24, 0.35, 2, "unverified"), ("8", 24, 0.5, 1, "verified"), ("9", 48, 0.6, 1, "verified")}
    report = build(con, "2026-11-23")
    assert report.startswith("# SIMULATED")
    assert "| Data classes | simulated |" in report
    assert "| RTX 4090 24GB | CN | 2 | $0.365 | $0.425 | $0.485 |" in report
    assert "| RTX 4090 48GB | CN | 1 | $0.600 | $0.600 | $0.600 |" in report
    assert "| RTX 4090 24GB | — | — | unavailable |" in report  # CN not-rentable search never ran
    assert "| Searches missing on this day | 15 of 16 |" in report


def test_schema_enforces_data_class_and_seeds_fx_default():
    con = connect(":memory:")
    assert con.execute("SELECT usd_cny FROM fx_rates").fetchone()[0] == 6.60
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO ledger (occurred_at, kind, amount, currency, source, data_class)"
                    " VALUES ('2026-11-23', 'electricity', -1, 'CNY', 'test', 'real')")
