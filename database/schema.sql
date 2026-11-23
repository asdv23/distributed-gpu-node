-- distributed-gpu-node schema (SQLite). database.connect() applies it idempotently on every open.
-- Once a deployed database holds data, schema changes ship as numbered scripts in database/migrations/.
--
-- data_class records where a fact comes from (docs/architecture.md#data-provenance):
--   verified      checked against a primary source
--   official_doc  taken from a platform's official documentation
--   collected     recorded by our own collector, agent or meter
--   third_party   someone else's dataset or report
--   estimate      output of a model
--   assumption    not yet verified
--   simulated     generated for tests or simulation; reports built from it are marked SIMULATED

-- ------------------------------------------------------------------ market data (Sprint 2)

-- One row per collector run, written before its first request, so a run that stored nothing still
-- counts in coverage. A run belongs to the UTC day it started.
CREATE TABLE IF NOT EXISTS market_runs (
    platform TEXT    NOT NULL,                  -- 'vast'
    run_id   TEXT    NOT NULL,                  -- UTC start of the run, 'YYYY-MM-DDTHH:MM:SSZ'
    planned  INTEGER NOT NULL,                  -- searches the run set out to send
    PRIMARY KEY (platform, run_id)
);

-- One row per API request, in the run run_id.
CREATE TABLE IF NOT EXISTS market_snapshots (
    id           INTEGER PRIMARY KEY,
    platform     TEXT    NOT NULL,              -- 'vast'
    run_id       TEXT    NOT NULL,              -- UTC start of the run, 'YYYY-MM-DDTHH:MM:SSZ'
    collected_at TEXT    NOT NULL,              -- UTC time the response arrived
    gpu_name     TEXT    NOT NULL,              -- slice: GPU model as the platform names it
    scope        TEXT    NOT NULL,              -- slice: key of SCOPES in the platform's collector
    rentable     INTEGER NOT NULL,              -- slice: value of the platform's 'rentable' filter
    auth         TEXT    NOT NULL CHECK (auth IN ('anonymous', 'api_key')),
    request      TEXT    NOT NULL,              -- exact JSON body sent
    offer_count  INTEGER NOT NULL,              -- offers in this response: a sample, not the full listing
    raw_gzip     BLOB    NOT NULL,              -- gzip(JSON response) with private fields removed
    data_class   TEXT    NOT NULL DEFAULT 'collected' CHECK (data_class IN
                 ('verified', 'official_doc', 'collected', 'third_party', 'estimate', 'assumption', 'simulated'))
);
CREATE INDEX IF NOT EXISTS market_snapshots_run ON market_snapshots (platform, run_id);

-- One normalised row per offer in a snapshot. Money in USD per hour.
CREATE TABLE IF NOT EXISTS market_offers (
    snapshot_id       INTEGER NOT NULL REFERENCES market_snapshots (id),
    offer_id          TEXT    NOT NULL,
    machine_id        TEXT,
    host_id           TEXT,                     -- for local analysis only; never published (docs/compliance.md)
    gpu_name          TEXT    NOT NULL,
    num_gpus          INTEGER NOT NULL,         -- GPUs in this offer
    machine_gpus      INTEGER,                  -- GPUs installed in the machine (num_gpus / gpu_frac)
    gpu_ram_mb        INTEGER,
    country           TEXT,                     -- ISO 3166-1 alpha-2, from the platform's 'Place, CC'
    region            TEXT,                     -- 'Place' part of the location
    verification      TEXT,                     -- 'verified' | 'unverified' | 'deverified'
    reliability       REAL,                     -- platform score, 0..1
    cpu_name          TEXT,
    cpu_cores         REAL,                     -- vCPUs allotted to this offer
    ram_mb            INTEGER,
    disk_gb           REAL,
    inet_up_mbps      REAL,
    inet_down_mbps    REAL,
    open_ports        INTEGER,
    price_type        TEXT    NOT NULL,         -- 'on-demand'
    price_usd_hr      REAL    NOT NULL,         -- listed GPU price of the whole offer (Vast dph_base)
    total_usd_hr      REAL,                     -- incl. storage at the API's default disk size (dph_total)
    min_bid_usd_hr    REAL,                     -- current interruptible minimum bid
    rentable          INTEGER,                  -- platform flag, semantics undocumented: NOT occupancy
    max_duration_days REAL,
    gpu_power_limit_w REAL,
    PRIMARY KEY (snapshot_id, offer_id)
);

-- ------------------------------------------ own hosts, rentals and money (Phase 2-3, Sprint 4)
-- Metric definitions these tables serve (docs/architecture.md#metrics):
--   Online Rate            = online hours / calendar hours
--   Rental Occupancy       = paid rental GPU-hours / listed GPU-hours
--   Productive Utilization = all actual compute GPU-hours / online GPU-hours (which intervals count
--                            as compute is settled in Sprint 4, see the architecture doc)
-- GPU Utilization comes from node-agent telemetry (Sprint 5) and never stands in for occupancy.

CREATE TABLE IF NOT EXISTS nodes (
    id        TEXT    PRIMARY KEY,              -- local name, e.g. 'gpu-host-1'
    gpu_model TEXT    NOT NULL,
    gpu_count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS node_intervals (
    id         INTEGER PRIMARY KEY,
    node_id    TEXT    NOT NULL REFERENCES nodes (id),
    state      TEXT    NOT NULL CHECK (state IN ('online', 'listed', 'internal_job', 'maintenance', 'fault')),
    gpu_count  INTEGER NOT NULL,                -- GPUs the interval covers
    started_at TEXT    NOT NULL,                -- UTC ISO-8601
    ended_at   TEXT,                            -- NULL while ongoing
    source     TEXT    NOT NULL,                -- e.g. 'vast-host-api', 'node-agent', 'manual'
    data_class TEXT    NOT NULL CHECK (data_class IN
               ('verified', 'official_doc', 'collected', 'third_party', 'estimate', 'assumption', 'simulated'))
);

-- One row per paid interval of a customer rental. When a platform stops billing GPU time inside one
-- contract (e.g. a stopped instance), each billed stretch is its own row with the same platform_ref.
CREATE TABLE IF NOT EXISTS rentals (
    id           INTEGER PRIMARY KEY,
    node_id      TEXT    NOT NULL REFERENCES nodes (id),
    platform     TEXT    NOT NULL,
    platform_ref TEXT,                          -- the platform's contract or instance id
    price_type   TEXT,                          -- 'on-demand' | 'interruptible' | 'reserved'
    gpu_count    INTEGER NOT NULL,
    started_at   TEXT    NOT NULL,
    ended_at     TEXT,
    source       TEXT    NOT NULL,
    data_class   TEXT    NOT NULL CHECK (data_class IN
                 ('verified', 'official_doc', 'collected', 'third_party', 'estimate', 'assumption', 'simulated'))
);

-- Money in its original currency: positive = in, negative = out. A 'payout' moves platform balance to
-- the bank and is neither revenue nor expense; 'hardware' is capital spend, depreciated separately.
CREATE TABLE IF NOT EXISTS ledger (
    id          INTEGER PRIMARY KEY,
    occurred_at TEXT    NOT NULL,
    node_id     TEXT    REFERENCES nodes (id),
    kind        TEXT    NOT NULL CHECK (kind IN ('rental_revenue', 'payout', 'electricity', 'network', 'repair',
                                                 'platform_fee', 'withdrawal_fee', 'hardware', 'other')),
    amount      REAL    NOT NULL,
    currency    TEXT    NOT NULL CHECK (currency IN ('USD', 'CNY')),
    rental_id   INTEGER REFERENCES rentals (id),
    source      TEXT    NOT NULL,
    data_class  TEXT    NOT NULL CHECK (data_class IN
                ('verified', 'official_doc', 'collected', 'third_party', 'estimate', 'assumption', 'simulated')),
    note        TEXT
);

-- USD->CNY. A conversion uses the rate with the latest effective_at not after the transaction (on a
-- tie, the higher id). The default applies from the start, so purchases made before the project
-- still convert.
CREATE TABLE IF NOT EXISTS fx_rates (
    id           INTEGER PRIMARY KEY,
    usd_cny      REAL NOT NULL,
    effective_at TEXT NOT NULL,
    source       TEXT NOT NULL,
    data_class   TEXT NOT NULL CHECK (data_class IN
                 ('verified', 'official_doc', 'collected', 'third_party', 'estimate', 'assumption', 'simulated'))
);
INSERT OR IGNORE INTO fx_rates (id, usd_cny, effective_at, source, data_class)
VALUES (1, 6.60, '1970-01-01T00:00:00Z', 'project default set by the operator on 2026-11-23; not a market quote',
        'assumption');
