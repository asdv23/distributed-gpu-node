"""Statistics from the public Clore.ai and Salad feeds in market_feeds, recomputed from the stored bodies."""
from __future__ import annotations

import gzip
import json
from sqlite3 import Connection


def clore_servers(con: Connection, day: str, gpus: tuple[str, ...]) -> tuple[list[tuple], int, int]:
    """Clore servers with a tracked GPU, one row per server and download of the UTC day.

    Rows are (model, gpus, country, rented, usd_per_gpu_hour or None). A model is GPU name plus memory
    class (4 GB steps, as for Vast). Servers that mix GPU models are left out, because the feed gives
    one memory size per server; their count in the day's last download is returned with the number
    of downloads.
    """
    rows, runs, mixed = [], 0, 0
    for (raw,) in con.execute("SELECT raw_gzip FROM market_feeds WHERE platform = 'clore' AND feed = 'servers'"
                              " AND substr(run_id, 1, 10) = ? ORDER BY run_id", (day,)):
        runs, mixed = runs + 1, 0
        for s in json.loads(gzip.decompress(raw))["all_servers"]:
            names = s["gpu_array"]
            if len(set(names)) > 1:
                mixed += 1
            elif names and names[0] in gpus:
                usd_day = s["price"].get("usd", {}).get("on_demand_usd")  # USD per server per day (official doc)
                rows.append((f"{names[0]} {4 * round(s['specs']['gpuram'] / 4)}GB", len(names), s["specs"]["net"]["cc"],
                             bool(s["rented"]), usd_day / 24 / len(names) if usd_day else None))
    return rows, runs, mixed


def latest(con: Connection, platform: str, feed: str, day: str) -> object | None:
    """Body of the last download of a feed on the UTC day, or None."""
    row = con.execute("SELECT raw_gzip FROM market_feeds WHERE platform = ? AND feed = ? AND substr(run_id, 1, 10) = ?"
                      " ORDER BY run_id DESC LIMIT 1", (platform, feed, day)).fetchone()
    return None if row is None else json.loads(gzip.decompress(row[0]))
