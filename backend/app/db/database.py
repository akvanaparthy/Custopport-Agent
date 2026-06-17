"""SQLite connection + schema lifecycle.

WAL mode so the dashboard can read while a run writes; foreign keys on.
Schema creation is idempotent (`CREATE TABLE IF NOT EXISTS`)."""
from __future__ import annotations

import pathlib
import sqlite3

SCHEMA_PATH = pathlib.Path(__file__).with_name("schema.sql")


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()
