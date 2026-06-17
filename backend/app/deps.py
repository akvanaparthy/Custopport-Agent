"""FastAPI dependencies. A request-scoped SQLite connection to the configured DB
(one connection per request — simplest correct choice for SQLite under WAL)."""
from __future__ import annotations

from typing import Iterator

from .config import get_settings
from .db.database import connect


def get_conn() -> Iterator:
    conn = connect(get_settings().db_path)
    try:
        yield conn
    finally:
        conn.close()
