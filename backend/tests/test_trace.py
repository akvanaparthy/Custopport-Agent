"""Tier-1: the trace recorder captures exactly what the Loom walkthrough needs —
per-step tool I/O, tokens, cost, latency, retries, and errors — and rolls up run
totals. No LLM, no network."""
from __future__ import annotations

import pytest

from app.db.database import connect
from app.observability.db import init_observability
from app.observability.trace_recorder import TraceRecorder


@pytest.fixture
def conn():
    c = connect(":memory:")
    init_observability(c)
    yield c
    c.close()


def _start(rec: TraceRecorder) -> str:
    return rec.start_run(
        conversation_id="conv_1", message_id="msg_1",
        identity_mode="authenticated", customer_id="cust_01", model="claude-sonnet-4-6",
    )


def test_records_steps_with_io_tokens_cost(conn):
    rec = TraceRecorder(conn)
    run_id = _start(rec)
    with rec.step(run_id, "llm", "gather") as h:
        h.set_input({"messages": 1})
        h.set_output({"text": "ok"})
        h.set_usage(input_tokens=1_000_000, output_tokens=0)
    rec.finish_run(run_id, final_verdict="APPROVE")

    step = conn.execute("SELECT * FROM steps WHERE run_id = ?", (run_id,)).fetchone()
    assert step["step_type"] == "llm"
    assert step["status"] == "ok"
    assert step["input_tokens"] == 1_000_000
    assert step["cost_usd"] == 3.0  # sonnet input $3/1M
    assert step["latency_ms"] >= 0

    run = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    assert run["status"] == "completed"
    assert run["final_verdict"] == "APPROVE"
    assert run["total_input_tokens"] == 1_000_000
    assert run["total_cost_usd"] == 3.0


def test_retry_folds_into_same_step_row(conn):
    rec = TraceRecorder(conn)
    run_id = _start(rec)
    with rec.step(run_id, "tool", "get_order") as h:
        h.record_retry({"type": "TransientToolError", "message": "boom"})
        h.set_output({"order_id": "ord_1"})  # succeeded on retry
    steps = conn.execute("SELECT * FROM steps WHERE run_id = ?", (run_id,)).fetchall()
    assert len(steps) == 1  # one row, not two
    assert steps[0]["retry_count"] == 1
    assert "TransientToolError" in steps[0]["attempts_json"]
    assert steps[0]["status"] == "ok"


def test_exception_is_recorded_and_reraised(conn):
    rec = TraceRecorder(conn)
    run_id = _start(rec)
    with pytest.raises(ValueError):
        with rec.step(run_id, "tool", "explode") as h:
            h.set_input({"x": 1})
            raise ValueError("kaboom")
    step = conn.execute("SELECT * FROM steps WHERE run_id = ?", (run_id,)).fetchone()
    assert step["status"] == "error"
    assert "kaboom" in step["error_json"]


def test_step_indexes_are_ordered(conn):
    rec = TraceRecorder(conn)
    run_id = _start(rec)
    for t in ("input_guard", "llm", "policy_engine", "action", "output_validation"):
        with rec.step(run_id, t, t):
            pass
    indexes = [r["step_index"] for r in conn.execute(
        "SELECT step_index FROM steps WHERE run_id = ? ORDER BY step_index", (run_id,)
    ).fetchall()]
    assert indexes == [0, 1, 2, 3, 4]
