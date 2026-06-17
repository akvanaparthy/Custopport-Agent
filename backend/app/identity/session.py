"""Server-side sessions — the canonical identity transport. The frontend gets a
session_id once and sends it as a header; the backend derives customer_id from
the session (never from the chat body). Authenticated sessions bind a customer at
creation; in_chat sessions stay unverified until a deterministic email+order
check passes. Verification is pure code here, not something the LLM can be talked
into."""
from __future__ import annotations

import secrets
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from ..agent.state import IdentityContext
from ..contracts import IdentityMode
from ..db import repository as repo


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row: Optional[sqlite3.Row]) -> Optional[dict]:
    return {k: row[k] for k in row.keys()} if row is not None else None


def create_session(conn: sqlite3.Connection, *, identity_mode: IdentityMode, customer_id: Optional[str]) -> dict:
    if identity_mode is IdentityMode.AUTHENTICATED:
        if not customer_id or repo.get_customer(conn, customer_id) is None:
            raise ValueError("authenticated mode requires a valid customer_id")
        verified = 1
    else:  # in_chat starts unverified, no bound customer
        customer_id, verified = None, 0

    session_id = "sess_" + secrets.token_urlsafe(18)
    conn.execute(
        "INSERT INTO sessions(session_id, identity_mode, customer_id, verified, created_at, last_seen) VALUES (?,?,?,?,?,?)",
        (session_id, identity_mode.value, customer_id, verified, _now(), _now()),
    )
    conn.commit()
    return get_session(conn, session_id)  # type: ignore[return-value]


def get_session(conn: sqlite3.Connection, session_id: str) -> Optional[dict]:
    return _row_to_dict(
        conn.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
    )


def verify_in_chat(conn: sqlite3.Connection, session_id: str, email: str, order_id: str) -> Optional[dict]:
    """Deterministic in_chat verification: the email must match a customer who
    OWNS the given order. On success, bind + verify the session. Returns None on
    any mismatch (caller maps to a failure)."""
    sess = get_session(conn, session_id)
    if sess is None or sess["identity_mode"] != IdentityMode.IN_CHAT.value:
        return None
    cust = conn.execute(
        "SELECT * FROM customers WHERE lower(email) = lower(?)", (email.strip(),)
    ).fetchone()
    if cust is None:
        return None
    if repo.get_order(conn, order_id, cust["customer_id"]) is None:  # ownership check
        return None
    conn.execute(
        "UPDATE sessions SET customer_id = ?, verified = 1, last_seen = ? WHERE session_id = ?",
        (cust["customer_id"], _now(), session_id),
    )
    conn.commit()
    return get_session(conn, session_id)


def to_identity(sess: dict) -> IdentityContext:
    return IdentityContext(
        mode=IdentityMode(sess["identity_mode"]),
        customer_id=sess["customer_id"],
        verified=bool(sess["verified"]),
    )
