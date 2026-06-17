"""Tier-1: session + chat endpoints via TestClient with a fake LLM (no key).
Covers the identity transport (session header, not customer in body) and the
in_chat verify gate."""
from __future__ import annotations

from app.deps import get_llm

from fakes import FakeLLM, classify


def _use_fake(client, *gather_rounds, respond_decision=None):
    client.app.dependency_overrides[get_llm] = lambda: FakeLLM(list(gather_rounds), respond_decision=respond_decision)


def test_customers_endpoint(client):
    assert len(client.get("/api/customers").json()) == 15


def test_authenticated_session_then_chat_approves(client):
    _use_fake(client, [classify("ord_clean", "damaged")])
    sess = client.post("/api/session", json={"customer_id": "cust_01"}).json()
    assert sess["verified"] == 1
    r = client.post("/api/chat", headers={"X-Session-Id": sess["session_id"]},
                    json={"message": "my headphones broke, refund please"})
    assert r.status_code == 200
    assert "event: final_message" in r.text
    assert "APPROVE" in r.text


def test_authenticated_rejects_invalid_customer(client):
    assert client.post("/api/session", json={"customer_id": "nope"}).status_code == 400


def test_chat_without_session_is_401(client):
    _use_fake(client, [classify("ord_clean", "damaged")])
    r = client.post("/api/chat", headers={"X-Session-Id": "bogus"}, json={"message": "hi"})
    assert r.status_code == 401


def test_in_chat_requires_verification(client):
    sess = client.post("/api/session", json={"identity_mode": "in_chat"}).json()
    assert sess["verified"] == 0
    # chat before verifying -> 403
    blocked = client.post("/api/chat", headers={"X-Session-Id": sess["session_id"]}, json={"message": "hi"})
    assert blocked.status_code == 403
    # verify with the right email+order, then chat works
    v = client.post("/api/session/verify", headers={"X-Session-Id": sess["session_id"]},
                    json={"email": "sarah.chen@example.com", "order_id": "ord_clean"})
    assert v.status_code == 200 and v.json()["verified"] == 1
    _use_fake(client, [classify("ord_clean", "damaged")])
    r = client.post("/api/chat", headers={"X-Session-Id": sess["session_id"]},
                    json={"message": "refund my broken headphones"})
    assert r.status_code == 200 and "event: final_message" in r.text


def test_in_chat_verify_rejects_unowned_order(client):
    sess = client.post("/api/session", json={"identity_mode": "in_chat"}).json()
    v = client.post("/api/session/verify", headers={"X-Session-Id": sess["session_id"]},
                    json={"email": "sarah.chen@example.com", "order_id": "ord_final"})
    assert v.status_code == 400


def test_my_orders_scoped_with_hints(client):
    sess = client.post("/api/session", json={"customer_id": "cust_01"}).json()
    h = {"X-Session-Id": sess["session_id"]}
    orders = client.get("/api/orders", headers=h).json()
    ids = {o["order_id"] for o in orders}
    assert "ord_clean" in ids and "ord_final" not in ids  # only own orders
    clean = next(o for o in orders if o["order_id"] == "ord_clean")
    assert clean["hint"]["tone"] == "eligible"
    assert client.get("/api/orders/ord_clean", headers=h).status_code == 200
    assert client.get("/api/orders/ord_final", headers=h).status_code == 404  # not owned


def test_my_orders_requires_session(client):
    assert client.get("/api/orders", headers={"X-Session-Id": "bad"}).status_code == 401
