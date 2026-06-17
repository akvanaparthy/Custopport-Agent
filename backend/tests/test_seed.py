"""Tier-1 tests for the data layer: seed idempotency, rule coverage, ownership
scoping, the refund guard, and the operator reset. No LLM, no network."""
from __future__ import annotations

from datetime import datetime

import pytest

from app.contracts import ClaimType, Decision
from app.db.database import connect, init_db
from app.db import repository as repo
from app.db.seed import ensure_seeded, _scenario_rows
from app.policy.engine import evaluate

NOW = datetime(2026, 6, 17, 12, 0, 0)


@pytest.fixture
def conn():
    c = connect(":memory:")
    init_db(c)
    ensure_seeded(c, NOW)
    yield c
    c.close()


def test_seed_is_idempotent():
    c = connect(":memory:")
    init_db(c)
    assert ensure_seeded(c, NOW) is True
    counts1 = (
        c.execute("SELECT COUNT(*) n FROM customers").fetchone()["n"],
        c.execute("SELECT COUNT(*) n FROM orders").fetchone()["n"],
    )
    assert ensure_seeded(c, NOW) is False  # second call is a no-op
    counts2 = (
        c.execute("SELECT COUNT(*) n FROM customers").fetchone()["n"],
        c.execute("SELECT COUNT(*) n FROM orders").fetchone()["n"],
    )
    assert counts1 == counts2 == (15, 15)
    c.close()


def test_fifteen_customers(conn):
    assert len(repo.list_customers(conn)) == 15


@pytest.mark.parametrize("order_id,claim,conf,expected,ref", list(_scenario_rows()))
def test_seeded_scenario_matches_engine(conn, order_id, claim, conf, expected, ref):
    owner = conn.execute(
        "SELECT customer_id FROM orders WHERE order_id = ?", (order_id,)
    ).fetchone()["customer_id"]
    ctx = repo.build_refund_context(
        conn, order_id, owner, claim_type=claim, claim_confidence=conf, now=NOW
    )
    assert ctx is not None
    verdict = evaluate(ctx)
    assert verdict.decision is expected
    assert ref in verdict.policy_refs


def test_every_terminal_decision_is_seeded():
    seen = {row[3] for row in _scenario_rows()}
    assert seen == {Decision.APPROVE, Decision.DENY, Decision.ESCALATE}


def test_ownership_scoping_blocks_cross_customer(conn):
    assert repo.get_order(conn, "ord_clean", "cust_01") is not None
    assert repo.get_order(conn, "ord_clean", "cust_02") is None  # not owned
    leaked = repo.build_refund_context(
        conn, "ord_clean", "cust_02", claim_type=ClaimType.DAMAGED, claim_confidence=0.9, now=NOW
    )
    assert leaked is None


def test_process_refund_guards_double_refund(conn):
    res = repo.process_refund(conn, "ord_clean", "cust_01", 120.0, NOW)
    assert res["refunded_amount"] == 120.0
    assert repo.get_order(conn, "ord_clean", "cust_01")["already_refunded"] == 1
    with pytest.raises(repo.AlreadyRefundedError):
        repo.process_refund(conn, "ord_clean", "cust_01", 120.0, NOW)


def test_process_refund_unowned_raises(conn):
    with pytest.raises(repo.OrderNotFoundError):
        repo.process_refund(conn, "ord_clean", "cust_02", 120.0, NOW)


def test_reset_order_clears_refund_linkage(conn):
    repo.process_refund(conn, "ord_clean", "cust_01", 120.0, NOW)
    assert repo.reset_order(conn, "ord_clean") is True
    row = repo.get_order(conn, "ord_clean", "cust_01")
    assert row["already_refunded"] == 0
    assert row["refunded_amount"] == 0
    assert row["refunded_at"] is None
    # the order is re-testable: a clean claim now approves again
    ctx = repo.build_refund_context(
        conn, "ord_clean", "cust_01", claim_type=ClaimType.DAMAGED, claim_confidence=0.95, now=NOW
    )
    assert evaluate(ctx).decision is Decision.APPROVE
