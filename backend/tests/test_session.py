"""Tier-1: server-side sessions. Authenticated binds a customer at creation;
in_chat verifies deterministically (email must own the order). No LLM, no key."""
from __future__ import annotations

from datetime import datetime

import pytest

from app.contracts import IdentityMode
from app.db.database import connect, init_db
from app.db.seed import ensure_seeded
from app.identity import session as sessions

NOW = datetime(2026, 6, 17, 12, 0, 0)


@pytest.fixture
def conn():
    c = connect(":memory:")
    init_db(c)
    ensure_seeded(c, NOW)
    yield c
    c.close()


def test_authenticated_binds_customer(conn):
    s = sessions.create_session(conn, identity_mode=IdentityMode.AUTHENTICATED, customer_id="cust_01")
    assert s["session_id"].startswith("sess_")
    assert s["customer_id"] == "cust_01"
    assert s["verified"] == 1


def test_authenticated_requires_valid_customer(conn):
    with pytest.raises(ValueError):
        sessions.create_session(conn, identity_mode=IdentityMode.AUTHENTICATED, customer_id="nope")
    with pytest.raises(ValueError):
        sessions.create_session(conn, identity_mode=IdentityMode.AUTHENTICATED, customer_id=None)


def test_in_chat_starts_unverified(conn):
    s = sessions.create_session(conn, identity_mode=IdentityMode.IN_CHAT, customer_id=None)
    assert s["verified"] == 0
    assert s["customer_id"] is None


def test_in_chat_verify_success_binds_customer(conn):
    s = sessions.create_session(conn, identity_mode=IdentityMode.IN_CHAT, customer_id=None)
    v = sessions.verify_in_chat(conn, s["session_id"], "sarah.chen@example.com", "ord_clean")
    assert v is not None
    assert v["verified"] == 1 and v["customer_id"] == "cust_01"


def test_in_chat_verify_rejects_unknown_email(conn):
    s = sessions.create_session(conn, identity_mode=IdentityMode.IN_CHAT, customer_id=None)
    assert sessions.verify_in_chat(conn, s["session_id"], "nobody@example.com", "ord_clean") is None


def test_in_chat_verify_rejects_unowned_order(conn):
    # Sarah (cust_01) does not own ord_final (cust_02) -> must fail
    s = sessions.create_session(conn, identity_mode=IdentityMode.IN_CHAT, customer_id=None)
    assert sessions.verify_in_chat(conn, s["session_id"], "sarah.chen@example.com", "ord_final") is None


def test_to_identity(conn):
    s = sessions.create_session(conn, identity_mode=IdentityMode.AUTHENTICATED, customer_id="cust_01")
    ident = sessions.to_identity(s)
    assert ident.mode is IdentityMode.AUTHENTICATED
    assert ident.customer_id == "cust_01"
    assert ident.verified is True
