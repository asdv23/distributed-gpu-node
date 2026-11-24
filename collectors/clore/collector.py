"""Clore.ai: the public marketplace server list, once per run.

    python -m collectors.clore.collector        env: GPU_NODE_DB

docs.clore.ai: "The marketplace listing is public"; prices in it are USD per server per day.
"""
from __future__ import annotations

import sys

from collectors import collect_feeds, setup_logging
from database import connect

FEEDS = {"servers": "https://clore.ai/webapi/marketplace/servers"}


def main() -> int:
    setup_logging()
    return 1 if collect_feeds(connect(), "clore", FEEDS) else 0


if __name__ == "__main__":
    sys.exit(main())
