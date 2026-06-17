"""Effective config = env defaults overlaid by the single SQLite override row.
Read fresh per request so an admin PUT takes effect on the next agent message.
The agent reads `get_effective_config(conn).max_tokens` (canonical key)."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Optional

from ..config import get_settings
from ..contracts import AgentSettings, Effort, IdentityMode
from .schema import SettingsUpdate, SettingsView

_BOOL_KEYS = {"adaptive_thinking", "input_guard_enabled", "output_validation_enabled"}


def _env_defaults() -> dict:
    s = get_settings()
    return {
        "model": s.default_model,
        "effort": s.default_effort,
        "adaptive_thinking": s.adaptive_thinking,
        "max_tokens": s.max_output_tokens,
        "input_guard_enabled": s.input_guard_enabled,
        "output_validation_enabled": s.output_validation_enabled,
        "identity_mode": s.identity_mode,
        "persona": s.persona,
    }


def _override_row(conn: sqlite3.Connection) -> Optional[dict]:
    row = conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()
    return {k: row[k] for k in row.keys()} if row is not None else None


def _effective(conn: sqlite3.Connection) -> tuple[dict, dict]:
    base = _env_defaults()
    source = {k: "env" for k in base}
    row = _override_row(conn)
    if row:
        for key in base:
            val = row.get(key)
            if val is None:
                continue
            base[key] = bool(val) if key in _BOOL_KEYS else val
            source[key] = "override"
    return base, source


def get_effective_config(conn: sqlite3.Connection) -> AgentSettings:
    base, _ = _effective(conn)
    return AgentSettings(**base)


def get_settings_view(conn: sqlite3.Connection) -> SettingsView:
    base, source = _effective(conn)
    return SettingsView(**base, source_map=source)


def update_settings(conn: sqlite3.Connection, patch: SettingsUpdate) -> SettingsView:
    norm: dict = {}
    for key, val in patch.model_dump(exclude_unset=True).items():
        if isinstance(val, (Effort, IdentityMode)):
            val = val.value
        elif isinstance(val, bool):
            val = int(val)
        norm[key] = val

    conn.execute("INSERT OR IGNORE INTO settings(id) VALUES (1)")
    if norm:
        assignments = ", ".join(f"{k} = ?" for k in norm)
        conn.execute(
            f"UPDATE settings SET {assignments}, updated_at = ? WHERE id = 1",
            (*norm.values(), datetime.now(timezone.utc).isoformat()),
        )
    conn.commit()
    return get_settings_view(conn)
