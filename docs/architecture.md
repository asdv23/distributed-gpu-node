# Architecture

## Goal and phases

The system grows in this order, and each phase must work before the next starts:

1. **Market research.** Collect GPU rental market data (Vast.ai first) as an hourly time series.
2. **Host occupancy tracking** (the most important module). Measure online time, listed time and
   paid rental time of our own node.
3. **Cost accounting.** Turn power, tariffs and fees into net operating cash flow.
4. **Node agent.** Read-only monitoring of the dedicated GPU host, reporting to the control plane.
5. **Scheduler.** One task model across rental platforms and our own jobs, simulation first.
6. Later: AI inference, fine-tuning, rendering and ZK-proof jobs, and joint scheduling with
   distributed energy.

## Components

```text
               ┌──────────────────── control plane (VPS) ─────────────────────┐
 Vast.ai API ─►│ collectors/ ──► SQLite (database/) ──► analytics/ ──► reports/ │
 (Clore, Salad,│                      ▲                     └──────► dashboard/ │
  Akash later) │                      │ node reports (Sprint 5)                 │
               └──────────────────────┼──────────────────────────────────────────┘
                                      │ WireGuard or Tailscale; no public SSH
               ┌──────────────────────┴────────── GPU host (execution node) ──────┐
               │ node-agent/: NVML and health checks, read-only, pushes to the VPS │
               │ platform host software (e.g. Vast host agent)                     │
               │ scheduler/adapters/: simulation only until the operator approves  │
               └───────────────────────────────────────────────────────────────────┘
```

The VPS is the control plane and the GPU host is the execution node. The host pushes its reports
to the VPS over the private overlay network. Nothing on either machine exposes SSH to the internet.

## Market data flow (Sprint 2)

1. `collectors/vast/collector.py` runs once an hour and sends 16 searches: 4 GPU names × the slices
   Global rentable, CN rentable, CN not rentable, Nearby rentable.
2. Each response becomes one `market_snapshots` row. The row holds the exact request and the gzip of
   the raw response, with IP addresses, hostnames, web pages and geocodes removed. Each offer also
   becomes one normalised `market_offers` row.
3. `analytics/pricing.py` reduces a UTC day of snapshots to one row per machine and slice.
   `analytics/market_report.py` renders `reports/market/YYYY-MM-DD.md` from those rows.

Two platform properties shape this design. Both were measured on 2026-11-23; see
[platform-research.md](platform-research.md).

- **Searches are sampled.** Identical searches return different subsets of the matching offers.
  One snapshot is a lower bound of supply, and the union of a day's hourly snapshots comes
  closer. The collector does not repeat searches to rebuild the full list (compliance).
- **Searches use a daily quota** of unknown size. 16 searches per hour is 384 a day. On a quota
  error the run stops at once.

A "model" is GPU name plus memory class (rounded to 4 GB). A 48 GB RTX 4090 is a different product
from a 24 GB one.

## Data provenance

Every operational fact carries a `data_class`: `verified`, `official_doc`, `collected`,
`third_party`, `estimate`, `assumption` or `simulated` (README). The database enforces the list
with `CHECK` constraints. A report built from any `simulated` row is titled SIMULATED.

## Metrics

| Metric | Formula | Inputs |
|---|---|---|
| Online Rate | online hours ÷ calendar hours | `node_intervals` state `online` |
| GPU Utilization | NVML utilisation over time | node-agent telemetry (Sprint 5) |
| Rental Occupancy | paid rental GPU-hours ÷ listed GPU-hours | `rentals` ÷ `node_intervals` state `listed` |
| Productive Utilization | (paid rental + internal job) GPU-hours ÷ online GPU-hours | `rentals`, `node_intervals` |
| Net Operating Cashflow | actual hosting revenue − all operating expenses | `ledger` |
| Break-even Occupancy | fixed operating cost per hour ÷ (listed GPUs × (net revenue − extra running cost) per rented GPU-hour) | cost model (Sprint 4) |

Rules:

- GPU Utilization never replaces Rental Occupancy. A busy GPU may be running our own job; an idle
  GPU may be rented and paid for.
- Revenue counts only what the platform reports as earned (`ledger.kind = 'rental_revenue'`, with
  its source). A `payout` moves money and is neither revenue nor expense.
- Hardware purchase (`kind = 'hardware'`) is depreciated separately. Phase 1 does not require it to
  be paid back.
- Amounts keep their original currency. USD→CNY uses `fx_rates`: the default is 6.60, a
  user-specified value with its source, and any newer row with its own source and time wins.

## Storage

SQLite (`database/schema.sql`) is applied idempotently on every connect. Once a deployed database
holds data, changes ship as numbered scripts in `database/migrations/`. Volume measured on the first
run: about 0.4 MB per run, so about 10 MB a day and under 4 GB a year at one run per hour.
PostgreSQL becomes worthwhile when several writers or the dashboard need concurrent access.

## Scheduler (Sprint 6, design constraints)

- **Adapters.** Each platform (Vast.ai, Clore.ai, own AI jobs, rendering, ZK proofs) implements one
  adapter interface. The core scheduler holds no platform-specific logic.
- **GPU exclusive lock.** A physical GPU serves at most one exclusive task at a time. Task types:
  external rental, AI inference, AI fine-tuning, rendering, ZK proof, internal job.
- **Priority** weighs expected revenue, energy cost, deadline, run time, memory requirement, GPU
  compatibility, pre-emption cost and contractual obligations, not price alone.
- **Contracts first.** A GPU rented by a customer stays with that customer until the rental ends.
  A higher offer elsewhere never interrupts it. Every platform switch follows that platform's current
  host terms.
- **Simulation only** in the first version. No real GPU or customer task is touched.

## Decisions

| Date | Decision | Why |
|---|---|---|
| 2026-11-23 | Standard library only (urllib, sqlite3, statistics, gzip) | no dependency was needed; Compose runs on the stock Python image |
| 2026-11-23 | SQLite, raw response plus normalised rows | recomputable analysis; one file to back up |
| 2026-11-23 | 16 searches per run, union over the day | sampled search plus a daily quota |
| 2026-11-23 | Model = GPU name + memory class | 48 GB RTX 4090 listings exist and are priced differently |
| 2026-11-23 | Host/machine IDs local only, no IPs stored | privacy; reports show aggregates |
