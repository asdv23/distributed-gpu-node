"""Listed-price and supply statistics over stored market snapshots. Reports recompute everything from here."""
from __future__ import annotations

from sqlite3 import Connection, Row
from statistics import quantiles


def p10_p50_p90(values: list[float]) -> tuple[float, float, float] | None:
    """Percentiles by linear interpolation between order statistics (numpy's default method)."""
    if not values:
        return None
    if len(values) == 1:
        return values[0], values[0], values[0]
    q = quantiles(values, n=10, method="inclusive")
    return q[0], q[4], q[8]


def machines_seen(con: Connection, day: str, platform: str = "vast") -> list[Row]:
    """One row per (slice, machine) seen by the runs that started on UTC day `day` (YYYY-MM-DD).

    vram_gb is the memory class, rounded to 4 GB: ECC-reduced cards (RTX 4090: 23028 MB) stay in their
    class and memory-modified boards (RTX 4090: 49140 MB) form their own. gpu_price is the lowest per-GPU
    price the machine listed in that slice during the day; the other columns come from that same
    observation (SQLite takes bare columns from the row of the single MIN). gpus is the number of
    GPUs installed in the machine. Searches are sampled, so the rows are a lower bound of supply.
    """
    return con.execute(
        """
        SELECT s.gpu_name, CAST(4 * ROUND(o.gpu_ram_mb / 4096.0) AS INTEGER) AS vram_gb,
               s.scope, s.rentable, o.machine_id,
               MIN(o.price_usd_hr / o.num_gpus) AS gpu_price,
               o.machine_gpus AS gpus, o.host_id, o.country, o.verification
        FROM market_snapshots s JOIN market_offers o ON o.snapshot_id = s.id
        WHERE s.platform = ? AND substr(s.run_id, 1, 10) = ?
        GROUP BY s.gpu_name, vram_gb, s.scope, s.rentable, o.machine_id
        """,
        (platform, day),
    ).fetchall()
