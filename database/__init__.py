"""SQLite access. The schema in schema.sql is applied on every connect (all statements are idempotent)."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

SCHEMA = Path(__file__).with_name("schema.sql")
DEFAULT_PATH = "data/gpu_node.db"


def connect(path: str | None = None) -> sqlite3.Connection:
    """Open the database at `path`, else $GPU_NODE_DB, else data/gpu_node.db (':memory:' works)."""
    path = path or os.environ.get("GPU_NODE_DB") or DEFAULT_PATH
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA.read_text())
    return con
