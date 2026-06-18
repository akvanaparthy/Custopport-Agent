"""Data access for the refund agent.

Reads used by the agent are ALWAYS ownership-scoped (order_id + customer_id), so
the agent can never see or act on another customer's order — the IDOR defense is
here in code, not in a prompt. `build_refund_context` computes
`days_since_delivery` from an INJECTED `now`, keeping the engine clock-free.
`process_refund` is the only money-moving write and guards against double
refunds. Admin helpers (status edit / reset / reset-seed) are operator-only and
live outside the agent's tool surface.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import date, datetime
from typing import Optional

from ..contracts import (
    ClaimType,
    Decision,
    ItemCondition,
    OrderStatus,
    RefundContext,
    Verdict,
)
from .seed import SEED_VERSION, ensure_seeded


class OrderNotFoundError(Exception):
    """Order does not exist or is not owned by the given customer."""


class AlreadyRefundedError(Exception):
    """The order has already been refunded; refusing a second refund."""


# --- reads ----------------------------------------------------------------- #


def list_customers(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT customer_id, name, email FROM customers ORDER BY customer_id"
    ).fetchall()


def get_customer(conn: sqlite3.Connection, customer_id: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM customers WHERE customer_id = ?", (customer_id,)
    ).fetchone()


def get_order(conn: sqlite3.Connection, order_id: str, customer_id: str) -> Optional[sqlite3.Row]:
    """Ownership-scoped: returns None if the order isn't owned by this customer."""
    return conn.execute(
        "SELECT * FROM orders WHERE order_id = ? AND customer_id = ?",
        (order_id, customer_id),
    ).fetchone()


def list_orders(conn: sqlite3.Connection, customer_id: Optional[str] = None) -> list[sqlite3.Row]:
    if customer_id is None:  # admin / operator view
        return conn.execute("SELECT * FROM orders ORDER BY order_id").fetchall()
    return conn.execute(
        "SELECT * FROM orders WHERE customer_id = ? ORDER BY order_id", (customer_id,)
    ).fetchall()


def _days_since(delivered_date: Optional[str], now: datetime) -> Optional[int]:
    if not delivered_date:
        return None
    return (now.date() - date.fromisoformat(delivered_date[:10])).days


def build_refund_context(
    conn: sqlite3.Connection,
    order_id: str,
    customer_id: str,
    *,
    claim_type: ClaimType,
    claim_confidence: float,
    now: datetime,
    item_condition: Optional[ItemCondition] = None,
) -> Optional[RefundContext]:
    """Build the engine's input from a verified, owned order + the LLM's claim
    classification. Returns None if the order isn't owned by this customer."""
    row = get_order(conn, order_id, customer_id)
    if row is None:
        return None
    return RefundContext(
        order_id=row["order_id"],
        customer_id=row["customer_id"],
        order_status=OrderStatus(row["status"]),
        days_since_delivery=_days_since(row["delivered_date"], now),
        order_total=row["order_total"],
        refund_amount=row["order_total"],  # v1: full-order refund
        is_final_sale=bool(row["is_final_sale"]),
        already_refunded=bool(row["already_refunded"]),
        category=row["category"],
        claim_type=claim_type,
        claim_confidence=claim_confidence,
        item_condition=item_condition or ItemCondition(row["item_condition"]),
    )


# --- writes ---------------------------------------------------------------- #


def log_verdict(
    conn: sqlite3.Connection,
    *,
    verdict: Verdict,
    order_id: str,
    customer_id: str,
    now: datetime,
    executed: bool,
) -> str:
    """Append a row to the refund ledger for any verdict. executed=1 only when
    money actually moved (APPROVE path)."""
    refund_id = "rf_" + uuid.uuid4().hex[:12]
    conn.execute(
        """INSERT INTO refunds(refund_id, order_id, customer_id, amount, decision,
               policy_refs, reasons, executed, created_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (
            refund_id, order_id, customer_id, verdict.refund_amount, verdict.decision.value,
            json.dumps(verdict.policy_refs), json.dumps(verdict.reasons),
            1 if executed else 0, now.isoformat(),
        ),
    )
    conn.commit()
    return refund_id


def process_refund(
    conn: sqlite3.Connection, order_id: str, customer_id: str, amount: float, now: datetime
) -> dict:
    """Execute an approved refund (the ONLY money-moving write). Ownership-scoped;
    guards against a double refund at the data layer (defense-in-depth behind the
    engine's P-ALREADY-REFUNDED)."""
    row = get_order(conn, order_id, customer_id)
    if row is None:
        raise OrderNotFoundError(f"{order_id} not found for {customer_id}")
    if row["already_refunded"]:
        raise AlreadyRefundedError(f"{order_id} already refunded")
    conn.execute(
        "UPDATE orders SET already_refunded = 1, refunded_amount = ?, refunded_at = ? WHERE order_id = ?",
        (amount, now.isoformat(), order_id),
    )
    conn.commit()
    return {"order_id": order_id, "refunded_amount": amount, "refunded_at": now.isoformat()}


# --- admin / operator (outside the agent's tool surface) ------------------- #


def update_order_status(conn: sqlite3.Connection, order_id: str, status: str) -> bool:
    cur = conn.execute("UPDATE orders SET status = ? WHERE order_id = ?", (status, order_id))
    conn.commit()
    return cur.rowcount > 0


def reset_order(conn: sqlite3.Connection, order_id: str, status: str = "delivered") -> bool:
    """Full reset so a refunded order can be re-tested: clear the refund linkage
    AND void any ledger rows — a status-only flip would leave the engine still
    denying on already_refunded."""
    cur = conn.execute(
        """UPDATE orders
           SET status = ?, already_refunded = 0, refunded_amount = 0, refunded_at = NULL
           WHERE order_id = ?""",
        (status, order_id),
    )
    conn.execute("DELETE FROM refunds WHERE order_id = ?", (order_id,))
    conn.commit()
    return cur.rowcount > 0


def reset_seed(conn: sqlite3.Connection, now: datetime) -> None:
    """Wipe and re-seed to pristine demo state."""
    ensure_seeded(conn, now, force=True)


# --- tickets (support history) -------------------------------------------- #


def create_ticket(
    conn: sqlite3.Connection,
    *,
    conversation_id: str,
    customer_id: str,
    customer_message: str,
    agent_reply: str,
    verdict: Optional[str],
    outcome: str,
    run_id: Optional[str],
    now: datetime,
) -> str:
    ticket_id = "tkt_" + uuid.uuid4().hex[:12]
    conn.execute(
        """INSERT INTO tickets(ticket_id, conversation_id, customer_id, customer_message,
               agent_reply, verdict, outcome, run_id, created_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (ticket_id, conversation_id, customer_id, customer_message, agent_reply,
         verdict, outcome, run_id, now.isoformat()),
    )
    conn.commit()
    return ticket_id


def list_tickets(conn: sqlite3.Connection, customer_id: str, limit: int = 50) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM tickets WHERE customer_id = ? ORDER BY created_at DESC LIMIT ?",
        (customer_id, limit),
    ).fetchall()


def list_conversation(conn: sqlite3.Connection, conversation_id: str, limit: int = 30) -> list[sqlite3.Row]:
    """Prior turns of ONE conversation, oldest first. The chat layer replays these
    as the message history so a follow-up ('the headphones', 'yes that one') keeps
    context across turns instead of being read in isolation."""
    return conn.execute(
        """SELECT customer_message, agent_reply FROM tickets
           WHERE conversation_id = ? ORDER BY created_at ASC LIMIT ?""",
        (conversation_id, limit),
    ).fetchall()
