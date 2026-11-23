"""Market data collectors, one sub-package per platform."""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime


class _JsonLines(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="seconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            **getattr(record, "data", {}),
        }
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def setup_logging(level: int = logging.INFO) -> None:
    """Structured logs: one JSON object per line on stderr. Pass fields with extra={"data": {...}}."""
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonLines())
    logging.basicConfig(level=level, handlers=[handler], force=True)
