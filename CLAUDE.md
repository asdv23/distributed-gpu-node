# Agent guide

Read README.md first: its ground rules and metric definitions bind every change.

## Data

- Tag every number in docs and reports with its `data_class` (table in README). Never present an
  estimate as revenue or a listing count as occupancy. Say *unavailable* when data cannot be had.
- Simulated data uses `data_class = 'simulated'`, and anything derived from it starts with
  "SIMULATED". Test fixtures carry a SIMULATED note.
- Store each raw platform response (minus private fields) next to its normalised rows, so every
  result can be recomputed from the database.
- Host and machine IDs stay in the local database. Reports and committed files carry aggregates
  only. Never store host IP addresses, hostnames or geocodes.

## Platforms

- Official APIs, official CLIs and public data only. Never bypass logins, captchas, access
  controls, quotas or result limits. For example, do not repeat a sampled search to rebuild the
  full list (docs/compliance.md).
- Every request has a timeout and a bounded retry with backoff, and stops on a quota error. Stay
  within documented and observed rate limits.
- Record platform behaviour you observe, with its date and evidence, in docs/platform-research.md.

## Secrets

- Never commit secrets. Code reads them from environment variables; `.env` is git-ignored.
  Never print or log a secret value.

## Real hardware

- Follow docs/security.md: read-only by default; the listed actions need a human's confirmation;
  the forbidden list has no exceptions.
- The scheduler runs as a simulation only until the operator decides otherwise.

## Work

- Follow the sprint order in README; do not build ahead of the current sprint.
- Python 3.12+, type hints, standard library first, JSON-lines logging (`collectors.setup_logging`).
- `python -m pytest` must pass. Every change is a commit and lands through a pull request.
