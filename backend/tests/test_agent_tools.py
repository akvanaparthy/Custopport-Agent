"""Tier-1: read-only tools are identity-scoped (IDOR defense in code), and the
cursed order produces a deterministic transient fault for the Loom retry."""
from __future__ import annotations

from datetime import datetime

import pytest

from app.agent.state import IdentityContext
from app.agent.tools import ToolRegistry, TransientToolError
from app.contracts import IdentityMode
from app.db.database import connect, init_db
from app.db.seed import CURSED_ORDER_ID, ensure_seeded

NOW = datetime(2026, 6, 17, 12, 0, 0)


@pytest.fixture
def conn():
    c = connect(":memory:")
    init_db(c)
    ensure_seeded(c, NOW)
    yield c
    c.close()


def _reg(conn, customer_id="cust_01", fault_enabled=True):
    return ToolRegistry(
        conn,
        IdentityContext(mode=IdentityMode.AUTHENTICATED, customer_id=customer_id),
        fault_enabled=fault_enabled,
    )


def test_get_my_orders_is_scoped(conn):
    ids = {o["order_id"] for o in _reg(conn, "cust_01").dispatch("get_my_orders", {})["orders"]}
    assert "ord_clean" in ids       # cust_01 owns it
    assert "ord_final" not in ids   # cust_02's order


def test_get_order_blocks_cross_customer(conn):
    reg = _reg(conn, "cust_01")
    assert reg.dispatch("get_order", {"order_id": "ord_clean"})["order_id"] == "ord_clean"
    assert reg.dispatch("get_order", {"order_id": "ord_final"}) == {"error": "order_not_found_for_customer"}


def test_cursed_order_transient_fault_then_succeeds(conn):
    reg = _reg(conn, "cust_10")  # owns the cursed order
    with pytest.raises(TransientToolError):
        reg.dispatch("get_order", {"order_id": CURSED_ORDER_ID})
    assert reg.dispatch("get_order", {"order_id": CURSED_ORDER_ID})["order_id"] == CURSED_ORDER_ID


def test_cursed_fault_can_be_disabled(conn):
    reg = _reg(conn, "cust_10", fault_enabled=False)
    assert reg.dispatch("get_order", {"order_id": CURSED_ORDER_ID})["order_id"] == CURSED_ORDER_ID


def test_classify_claim_is_terminal_signal(conn):
    out = _reg(conn, "cust_01").dispatch(
        "classify_claim", {"order_id": "ord_clean", "claim_type": "damaged", "confidence": 0.9}
    )
    assert out == {"ok": True}


def test_policy_summary_available(conn):
    assert "policy" in _reg(conn, "cust_01").dispatch("get_policy_summary", {})
