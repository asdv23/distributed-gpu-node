"""Daily market report: reports/market/YYYY-MM-DD.md from one UTC day of Vast snapshots.

    python -m analytics.market_report [YYYY-MM-DD]      env: GPU_NODE_DB; default day: latest in the DB

Every figure is recomputed from the stored snapshots via analytics/pricing.py.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path
from sqlite3 import Connection, Row

from analytics.pricing import machines_seen, p10_p50_p90
from collectors.vast.collector import GPUS, SCOPES, SLICES, URL
from database import connect

OUT_DIR = Path("reports/market")
SCOPE_NAME = {"GLOBAL": "Global", "CN": "CN", "NEARBY": "Nearby"}
VERIFICATION = ("verified", "unverified", "deverified")


def _usd(x: float | None) -> str:
    return "—" if x is None else f"${x:.3f}"


def _p50(rows: list[Row]) -> str:
    p = p10_p50_p90([r["gpu_price"] for r in rows])
    return "—" if p is None else f"{_usd(p[1])} (n={len(rows)})"


def _table(header: list[str], rows: list[list[object]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    return lines + ["| " + " | ".join(str(c) for c in row) + " |" for row in rows] + [""]


def build(con: Connection, day: str) -> str:
    runs = con.execute("SELECT run_id, planned FROM market_runs WHERE platform = 'vast' AND substr(run_id, 1, 10) = ?"
                       " ORDER BY run_id", (day,)).fetchall()
    if not runs:
        raise SystemExit(f"no Vast collection runs on {day}")
    snaps = con.execute(
        "SELECT run_id, gpu_name, scope, rentable, offer_count, auth, data_class FROM market_snapshots"
        " WHERE platform = 'vast' AND substr(run_id, 1, 10) = ? ORDER BY id", (day,)).fetchall()
    planned = sum(r["planned"] for r in runs)
    earlier_days = con.execute(
        "SELECT COUNT(DISTINCT substr(run_id, 1, 10)) FROM market_snapshots"
        " WHERE platform = 'vast' AND substr(run_id, 1, 10) < ?", (day,)).fetchone()[0]
    sizes: dict[tuple, list[int]] = defaultdict(list)
    for s in snaps:
        sizes[(s["gpu_name"], s["scope"], bool(s["rentable"]))].append(s["offer_count"])
    machines = machines_seen(con, day)
    # a model is GPU name + memory class: memory-modified boards are a different product. A GPU with
    # no machine seen keeps its rows, so missing or empty searches stay visible.
    seen_names = {m["gpu_name"] for m in machines}
    models = sorted({(m["gpu_name"], m["vram_gb"]) for m in machines} | {(g, None) for g in GPUS if g not in seen_names},
                    key=lambda g: (GPUS.index(g[0]) if g[0] in GPUS else len(GPUS), g[1]))
    seen: dict[tuple, list[Row]] = defaultdict(list)
    for m in machines:
        seen[(m["gpu_name"], m["vram_gb"], m["scope"], bool(m["rentable"]))].append(m)
    names = {g: f"{g[0]} {g[1]}GB" if g[1] else g[0] for g in models}

    out = [f"# Vast.ai GPU market — {day} (UTC)", ""]
    if any(s["data_class"] == "simulated" for s in snaps):
        out[0] = f"# SIMULATED — Vast.ai GPU market — {day} (UTC)"
        out += ["> **SIMULATED DATA. Not market data; do not cite.**", ""]
    out += [
        "Listings and listed prices seen in the Vast.ai public search API; the data classes are in the",
        "table below. The searches are sampled (§1), so counts are lower bounds. Nothing here is a rental",
        "rate, an occupancy rate or host revenue.",
        "",
        *_table(["Item", "Value"], [
            ["Collection runs", f"{len(runs)} ({runs[0]['run_id']} … {runs[-1]['run_id']}); a run belongs to "
                                "the UTC day it started"],
            ["Searches stored", f"{len(snaps)} of {planned} planned"],
            ["Data classes", ", ".join(sorted({s["data_class"] for s in snaps})) or "—"],
            ["Auth", ", ".join(sorted({s['auth'] for s in snaps})) or "—"],
            ["Endpoint", f"`POST {URL}` (request shape of the official vastai CLI)"],
            ["Price", "on-demand listed GPU price (`dph_base` ÷ GPUs in the offer), USD per GPU-hour"],
        ]),
        "## 1. Method and limits",
        "",
        "- **Slices.** Per GPU name, one search each: Global rentable · CN (mainland China) rentable ·",
        f"  CN not rentable · Nearby rentable ({' '.join(SCOPES['NEARBY'])}). Each scope is its own sample.",
        "- **Every response is a sample** (collected, 2026-11-23): six identical searches returned 37 offers",
        "  each but 96 distinct offers on 58 machines between them, still growing (KR, RTX 3060). A",
        "  third-party report says an API key does not change this",
        "  ([vast-cli#536](https://github.com/vast-ai/vast-cli/issues/536), unanswered by Vast). Machine",
        "  counts are lower bounds; the union of a day's hourly runs comes closer. Responses without an",
        "  API key never exceed 64 offers.",
        "- **Machines, not offers.** A machine listed in several sizes (1, 2, 4 … GPUs) counts once, at the",
        "  lowest per-GPU price it listed that day. GPUs installed = GPUs in the offer ÷ `gpu_frac`.",
        "- **Models include memory.** Memory is rounded to 4 GB, so ECC-reduced cards stay in their class.",
        "  NVIDIA's RTX 4090 has 24 GB (official spec); 48 GB listings are presumably memory-modified",
        "  boards (assumption) and are reported as their own model.",
        "- **Percentiles** P10 / P50 / P90 over machines, linear interpolation. Below n=5 they say little.",
        "- **`rentable`** is a platform flag with undocumented meaning: a machine that is not rentable may be",
        "  rented, offline or reserved. It is not occupancy. The API's `rented` flag refers to the caller's",
        "  own rentals (official doc) and is not used.",
        "",
        "## 2. Supply seen (machines, lower bounds)",
        "",
    ]
    rows = []
    for g in models:
        for scope, rentable in SLICES:
            ms = seen[(*g, scope, rentable)]
            n = sizes[(g[0], scope, rentable)]
            rows.append([names[g], f"{SCOPE_NAME[scope]} · {'rentable' if rentable else 'not rentable'}", len(ms),
                         len({m["host_id"] for m in ms}), sum(m["gpus"] or 0 for m in ms),
                         f"{min(n)}–{max(n)}" if n else "missing"])
    out += _table(["Model", "Slice", "Machines", "Hosts", "GPUs installed", "Offers per search (all memory sizes)"],
                  rows)

    out += ["## 3. Listed on-demand price per GPU-hour (rentable machines)", ""]
    rows = []
    for g in models:
        for scope, rentable in SLICES:
            if rentable:
                ms = seen[(*g, scope, True)]
                p = p10_p50_p90([m["gpu_price"] for m in ms])
                rows.append([names[g], SCOPE_NAME[scope], len(ms), *(map(_usd, p) if p else ["—"] * 3)])
    out += _table(["Model", "Scope", "Machines", "P10", "P50", "P90"], rows)

    out += ["## 4. Verified vs unverified (rentable machines, P50 per GPU-hour)", ""]
    rows = []
    for g in models:
        for scope, rentable in SLICES:
            if rentable:
                ms = seen[(*g, scope, True)]
                rows.append([names[g], SCOPE_NAME[scope], *(_p50([m for m in ms if m["verification"] == v])
                                                           for v in VERIFICATION)])
    out += _table(["Model", "Scope", *VERIFICATION], rows)

    out += ["## 5. China mainland and nearby markets, by country (rentable machines)", "",
            "Machines seen · P50 per GPU-hour. CN from the CN search, the others from the Nearby search;",
            "countries with no machine seen are left out.", ""]
    by_country: dict[str, dict[tuple, list[Row]]] = defaultdict(lambda: defaultdict(list))
    for g in models:
        for scope in ("CN", "NEARBY"):
            for m in seen[(*g, scope, True)]:
                by_country[m["country"] or "?"][g].append(m)
    order = sorted(by_country, key=lambda c: (c != "CN", -sum(map(len, by_country[c].values())), c))
    rows = [[c, *(f"{len(ms)} · {_usd(p10_p50_p90([m['gpu_price'] for m in ms])[1])}" if (ms := by_country[c][g])
                  else "—" for g in models)] for c in order]
    out += _table(["Country", *names.values()], rows)

    out += ["## 6. Listing status in China mainland (observable flag, not occupancy)", "",
            "Machines with at least one rentable offer vs machines seen only in the not-rentable search.",
            "Sampled searches and an undocumented flag: this is neither occupancy nor demand. Unavailable",
            "unless both CN searches for the model succeeded at least once that day.", ""]
    rows = []
    for g in models:
        if not (sizes[(g[0], "CN", True)] and sizes[(g[0], "CN", False)]):
            rows.append([names[g], "—", "—", "unavailable"])
            continue
        yes = {m["machine_id"] for m in seen[(*g, "CN", True)]}
        only_no = {m["machine_id"] for m in seen[(*g, "CN", False)]} - yes
        total = len(yes) + len(only_no)
        rows.append([names[g], len(yes), len(only_no), f"{len(only_no) / total:.0%}" if total else "—"])
    out += _table(["Model", "Rentable", "Seen only not rentable", "Share not rentable"], rows)

    out += ["## 7. Supply and demand changes", "",
            "Unavailable: " + ("this is the first day of collection." if not earlier_days else
                               f"{earlier_days} earlier day(s) are stored; day-over-day and 7/30/90-day "
                               "comparisons arrive with Sprint 3."), ""]

    out += ["## 8. Data gaps", ""]
    out += _table(["Item", "Status"], [
        ["Rental status and occupancy of other hosts", "unavailable: no public source; `rentable` is not occupancy"],
        ["Demand (rentals started, hours rented)", "unavailable: no public source"],
        ["Host payout per GPU-hour", "unavailable: Vast's fee split with hosts not yet verified"],
        ["Complete supply counts", "unavailable: searches are sampled, counts above are lower bounds"],
        ["Not-rentable listings outside CN", "not collected (daily search quota)"],
        ["Searches missing on this day", f"{planned - len(snaps)} of {planned}"],
    ])

    out += ["## 9. Investment and operating risks", "", "Qualitative. Each item carries its data class.", "",
            "- **[collected]** Listings are not rentals. Nothing here shows how many hours any host is paid",
            "  for, so break-even cannot be judged from prices alone.",
            "- **[assumption]** Host income per GPU-hour is below the listed price: Vast's fee split, idle time",
            "  between rentals and storage or bandwidth charges all apply. To verify from host documentation",
            "  and real payouts (Sprint 4).",
            "- **[assumption]** At low occupancy, electricity and cooling at the operator's tariff can exceed",
            "  income, most of all for the high-power cards. The cost model needs measured power (Sprint 4-5).",
            "- **[assumption]** Hosts in mainland China may attract fewer renters: cross-border bandwidth and",
            "  latency, and restricted access to overseas registries (Docker Hub, Hugging Face). To be",
            "  measured on the operator's machine.",
            "- **[assumption]** Older cards lose price as newer ones (RTX 5090) arrive; 30/90-day trends will",
            "  show whether this holds.",
            "- **[third_party]** Platform behaviour changes without notice: one search returned about half",
            "  of the offers seen across a reporter's repeated searches in September 2026, and 10-30% by",
            "  November (vast-cli#536).",
            "- **[assumption]** Round-the-clock load wears consumer cards (fans, thermal pads, memory",
            "  temperature on the RTX 3090). Depreciation is tracked apart from operating cash flow.",
            ""]
    return "\n".join(out)


def main() -> int:
    con = connect()
    day = sys.argv[1] if len(sys.argv) > 1 else con.execute(
        "SELECT substr(MAX(run_id), 1, 10) FROM market_runs WHERE platform = 'vast'").fetchone()[0]
    if day is None:
        raise SystemExit("no Vast collection runs in the database")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{day}.md"
    path.write_text(build(con, day), encoding="utf-8")
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
