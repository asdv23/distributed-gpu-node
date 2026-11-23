# distributed-gpu-node

Research and operations toolkit for one person's GPU hosting. It watches the GPU rental markets,
measures what a hosted node really earns and costs, and will later schedule that node's GPUs
across rental platforms and its own jobs.

**Status, 2026-11-23:** Sprint 1 is done and Sprint 2 is under way. The Vast.ai market collector
runs, and the first market report is in [`reports/market/`](reports/market/). Nothing controls real
hardware yet.

## What has to be proven first

Can hosting income cover the node's running costs? Phase 1 passes after **30 consecutive days in
which actual hosting revenue covers electricity and every other operating expense**. Hardware
purchase is depreciated separately and is not part of that test.

## Ground rules

1. Real data before models. Simulation before device control. Proven cost coverage before scale.
2. Every number carries its provenance, stored as `data_class`:

   | `data_class` | 中文 | Meaning |
   |---|---|---|
   | `verified` | 已验证事实 | checked against a primary source |
   | `official_doc` | 官方文档 | from a platform's official documentation |
   | `collected` | 实际采集数据 | recorded by our own collector, agent or meter |
   | `third_party` | 第三方数据 | someone else's dataset or report |
   | `estimate` | 模型估算 | output of a model |
   | `assumption` | 尚未验证的假设 | not verified yet |
   | `simulated` | 模拟数据 | generated; anything built from it is marked **SIMULATED** |

   An estimate is never reported as revenue, and a listing count is never reported as an occupancy
   rate. Data that cannot be had is marked *unavailable*.
3. Official APIs, official CLIs and public data only. No bypassing logins, captchas, access
   controls or platform limits ([compliance](docs/compliance.md)).
4. No secrets, tokens, passwords or customer data in this repository ([security](docs/security.md)).

## Metrics

| Metric | Definition | Source |
|---|---|---|
| Online Rate | online hours ÷ calendar hours | node agent |
| GPU Utilization | share of time the GPU computes (NVML) | node agent |
| Rental Occupancy | paid rental GPU-hours ÷ listed GPU-hours | platform host data |
| Productive Utilization | all actual compute GPU-hours ÷ online GPU-hours | platform host data + agent |
| Net Operating Cashflow | actual hosting revenue − all operating expenses | ledger |

GPU Utilization never stands in for Rental Occupancy. Details are in
[docs/architecture.md](docs/architecture.md#metrics).

## Quick start

Python 3.12+, standard library only (pytest for the tests).

```sh
python -m collectors.vast.collector    # one collection run (16 searches) into data/gpu_node.db
python -m analytics.market_report      # writes reports/market/<UTC day>.md
pip install pytest && python -m pytest
```

Hourly collection on the control-plane VPS:

```sh
cp .env.example .env     # optional: VAST_API_KEY
docker compose up -d     # one run per hour, then today's report is rewritten
```

The service writes `data/` and `reports/` in the checkout. With rootful Docker it writes them as
root, so either run it from a root-owned checkout or add `user: "<uid>:<gid>"` of the checkout owner
to the service.

### Deployment checkout and published reports

Collection runs from a deployment checkout that stays on `main` and is the only writer of
`reports/market/`. Development happens in another checkout. On the agent host the deployment
checkout is a separate clone, run from its owner's crontab:

```cron
11 * * * *  cd <checkout> && mkdir -p data && flock -n data/collector.lock sh -c 'python3 -m collectors.vast.collector; python3 -m analytics.market_report'
41 2 * * *  cd <checkout> && mkdir -p data && flock -w 300 data/collector.lock timeout 600 scripts/publish_reports.sh   # once a day, any hour
```

`scripts/publish_reports.sh` fast-forwards to `origin/main` (so the deployment picks up merged
code), commits the reports of finished UTC days and pushes them. Local `main` never keeps a commit of
its own: a failed push is undone and retried on the next run, and the script refuses to run while
local `main` holds commits that are not on `origin/main`. To regenerate a past report, run
`flock data/collector.lock python3 -m analytics.market_report YYYY-MM-DD` in the deployment checkout;
the next publish run commits it. The Compose service only collects: publishing needs git and push
access on the host.

## Repository layout

| Path | Contents | Sprint |
|---|---|---|
| `docs/` | architecture, platform research, host requirements, security, GPU hardware, compliance | 1 |
| `database/` | SQLite schema (`schema.sql`); later changes go in `migrations/` | 1 |
| `collectors/vast/` | Vast.ai market collector | 2 |
| `analytics/pricing.py`, `analytics/market_report.py` | market statistics and the daily report | 2–3 |
| `reports/market/` | generated market reports | 2+ |
| `analytics/occupancy.py`, `revenue.py`, `energy_cost.py` | operations metrics and cost model (not written yet) | 4 |
| `reports/operations/` | operations reports | 4+ |
| `node-agent/` | read-only monitoring agent for the GPU host | 5 |
| `scheduler/`, `scheduler/adapters/` | simulated multi-platform scheduler | 6 |
| `dashboard/` | web dashboard | after 4 |
| `collectors/clore/`, `salad/`, `akash/` | other markets | later |
| `research/` | dated research notes: platforms, GPU markets, energy | ongoing |

Empty directories hold a `.gitkeep` until their sprint starts.

## Roadmap

| Sprint | Scope | State |
|---|---|---|
| 1 | Repository, docs, data model, CI | done |
| 2 | Vast market collection: collector, first batch, hourly history | collector and first batch done; hourly deployment pending |
| 3 | Market analysis: price distribution, supply and listing-status changes, competition | next |
| 4 | Operations accounting: electricity model, real income, occupancy, cash-flow balance | |
| 5 | Node agent: read-only hardware monitoring, power, health checks, reporting | |
| 6 | Simulated scheduler: platform adapters, GPU exclusive lock, priorities, pre-emption | |

## License

[MIT](LICENSE)
