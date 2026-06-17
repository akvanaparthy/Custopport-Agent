"""Tier-1: the admin API end to end via TestClient (no API key). Exercises real
wiring — lifespan init+seed, request-scoped DB dependency, serializers."""
from __future__ import annotations

from app.config import get_settings
from app.db.database import connect
from app.observability.trace_recorder import TraceRecorder


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_orders_seeded(client):
    orders = client.get("/api/admin/orders").json()
    assert len(orders) == 15
    ids = {o["order_id"] for o in orders}
    assert {"ord_clean", "ord_cursed", "ord_final"} <= ids


def test_get_order_404(client):
    assert client.get("/api/admin/orders/nope").status_code == 404


def test_settings_defaults(client):
    body = client.get("/api/admin/settings").json()
    assert body["model"] == "claude-sonnet-4-6"
    assert body["source_map"]["model"] == "env"


def test_settings_override_persists(client):
    r = client.put("/api/admin/settings", json={"model": "claude-haiku-4-5", "effort": "low"})
    assert r.status_code == 200
    body = r.json()
    assert body["model"] == "claude-haiku-4-5" and body["effort"] == "low"
    assert body["source_map"]["model"] == "override"
    assert client.get("/api/admin/settings").json()["model"] == "claude-haiku-4-5"


def test_settings_rejects_sampling_params(client):
    assert client.put("/api/admin/settings", json={"temperature": 0.5}).status_code == 422


def test_settings_rejects_bad_model(client):
    assert client.put("/api/admin/settings", json={"model": "gpt-4"}).status_code == 422


def test_settings_rejects_high_max_tokens(client):
    assert client.put("/api/admin/settings", json={"max_tokens": 64000}).status_code == 422


def test_order_edit_and_full_reset(client):
    r = client.put("/api/admin/orders/ord_clean", json={"status": "shipped"})
    assert r.status_code == 200 and r.json()["status"] == "shipped"
    r = client.post("/api/admin/orders/ord_clean/reset")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "delivered"
    assert body["already_refunded"] is False
    assert body["refunded_amount"] == 0


def test_reset_seed(client):
    body = client.post("/api/admin/reset-seed").json()
    assert body["ok"] is True and body["customers"] == 15 and body["orders"] == 15


def _make_run(verdict: str = "APPROVE") -> str:
    conn = connect(get_settings().db_path)
    rec = TraceRecorder(conn)
    run_id = rec.start_run(
        conversation_id="c1", message_id="m1",
        identity_mode="authenticated", customer_id="cust_01", model="claude-sonnet-4-6",
    )
    with rec.step(run_id, "policy_engine", "evaluate") as h:
        h.set_input({"order": "ord_clean"})
        h.set_output({"decision": verdict})
    rec.finish_run(run_id, final_verdict=verdict)
    conn.close()
    return run_id


def test_runs_list_and_detail(client):
    run_id = _make_run("APPROVE")
    data = client.get("/api/admin/runs").json()
    assert data["total"] >= 1
    assert any(r["run_id"] == run_id for r in data["runs"])

    detail = client.get(f"/api/admin/runs/{run_id}").json()
    assert detail["final_verdict"] == "APPROVE"
    assert len(detail["steps"]) == 1
    assert detail["steps"][0]["step_type"] == "policy_engine"
    assert detail["steps"][0]["output"]["decision"] == "APPROVE"


def test_run_detail_404(client):
    assert client.get("/api/admin/runs/nope").status_code == 404


def test_run_stream_finished(client):
    run_id = _make_run("DENY")
    r = client.get(f"/api/admin/runs/{run_id}/stream")
    assert r.status_code == 200
    assert "event: step" in r.text
    assert "event: done" in r.text
