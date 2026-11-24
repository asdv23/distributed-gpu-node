"""Salad: the published host earning rates and the GPU demand monitor, once per run.

    python -m collectors.salad.collector        env: GPU_NODE_DB

Both are public, no-login JSON that Salad's own site reads.
"""
from __future__ import annotations

import sys

from collectors import collect_feeds, setup_logging
from database import connect

FEEDS = {
    "earning-rates": ("https://cdn.salad.com/site-data/earning-rates.json",
                      lambda d: isinstance(d, dict) and isinstance(d.get("classes"), list)),
    "demand-monitor": ("https://app-api.salad.com/api/v2/demand-monitor/gpu", lambda d: isinstance(d, list)),
}


def main() -> int:
    setup_logging()
    return 1 if collect_feeds(connect(), "salad", FEEDS) else 0


if __name__ == "__main__":
    sys.exit(main())
