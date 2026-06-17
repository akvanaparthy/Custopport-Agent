"""Admin API the operator console consumes: runs + trace drill-down, runtime
settings, and operator order management. The order endpoints write via the
repository on an admin-only path — they are NOT in the agent's tool surface."""
from __future__ import annotations

import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..contracts import OrderStatus
from ..db import repository as repo
from ..deps import get_conn
from ..settings import store as settings_store
from ..settings.schema import SettingsUpdate, SettingsView
from . import serializers as S

router = APIRouter(prefix="/api/admin", tags=["admin"])


# --- runs + trace --------------------------------------------------------- #


@router.get("/runs")
def list_runs(limit: int = 50, offset: int = 0, conn=Depends(get_conn)):
    total = conn.execute("SELECT COUNT(*) AS n FROM runs").fetchone()["n"]
    rows = conn.execute(
        "SELECT * FROM runs ORDER BY started_at DESC LIMIT ? OFFSET ?", (limit, offset)
    ).fetchall()
    runs = []
    for r in rows:
        sc = conn.execute(
            "SELECT COUNT(*) AS n FROM steps WHERE run_id = ?", (r["run_id"],)
        ).fetchone()["n"]
        runs.append(S.to_run_summary(r, sc))
    return {"runs": runs, "total": total, "limit": limit, "offset": offset}


@router.get("/runs/{run_id}", response_model=S.RunDetail)
def get_run(run_id: str, conn=Depends(get_conn)):
    row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="run not found")
    steps = conn.execute(
        "SELECT * FROM steps WHERE run_id = ? ORDER BY step_index", (run_id,)
    ).fetchall()
    return S.to_run_detail(row, steps)


@router.get("/runs/{run_id}/stream")
def stream_run(run_id: str, conn=Depends(get_conn)):
    """SSE live tail: emit each new step, then a run_update + done when the run
    leaves 'running'. Finished runs stream their steps and close immediately."""

    def gen():
        last = -1
        for _ in range(60):  # bounded poll (~12s) so it never hangs forever
            rows = conn.execute(
                "SELECT * FROM steps WHERE run_id = ? AND step_index > ? ORDER BY step_index",
                (run_id, last),
            ).fetchall()
            for r in rows:
                last = r["step_index"]
                yield f"event: step\ndata: {S.to_step_view(r).model_dump_json()}\n\n"
            run = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if run is None:
                yield 'event: error\ndata: {"detail":"run not found"}\n\n'
                return
            if run["status"] != "running":
                yield f"event: run_update\ndata: {S.to_run_summary(run, last + 1).model_dump_json()}\n\n"
                yield "event: done\ndata: {}\n\n"
                return
            time.sleep(0.2)
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


# --- settings ------------------------------------------------------------- #


@router.get("/settings", response_model=SettingsView)
def get_settings_endpoint(conn=Depends(get_conn)):
    return settings_store.get_settings_view(conn)


@router.put("/settings", response_model=SettingsView)
def put_settings_endpoint(patch: SettingsUpdate, conn=Depends(get_conn)):
    return settings_store.update_settings(conn, patch)


# --- operator order management (NOT an agent capability) ------------------ #


class OrderStatusUpdate(BaseModel):
    status: OrderStatus


@router.get("/orders", response_model=list[S.OrderView])
def list_orders(conn=Depends(get_conn)):
    return [S.to_order_view(r) for r in repo.list_orders(conn)]


@router.get("/orders/{order_id}", response_model=S.OrderView)
def get_order(order_id: str, conn=Depends(get_conn)):
    row = conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="order not found")
    return S.to_order_view(row)


@router.put("/orders/{order_id}", response_model=S.OrderView)
def edit_order_status(order_id: str, body: OrderStatusUpdate, conn=Depends(get_conn)):
    if not repo.update_order_status(conn, order_id, body.status.value):
        raise HTTPException(status_code=404, detail="order not found")
    row = conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
    return S.to_order_view(row)


@router.post("/orders/{order_id}/reset", response_model=S.OrderView)
def reset_order(order_id: str, conn=Depends(get_conn)):
    """Full reset (clears refund linkage + voids ledger rows) so the order is
    re-testable — a status-only flip would leave the engine denying."""
    if not repo.reset_order(conn, order_id):
        raise HTTPException(status_code=404, detail="order not found")
    row = conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
    return S.to_order_view(row)


@router.post("/reset-seed")
def reset_seed(conn=Depends(get_conn)):
    repo.reset_seed(conn, datetime.now(timezone.utc))
    return {
        "ok": True,
        "customers": conn.execute("SELECT COUNT(*) AS n FROM customers").fetchone()["n"],
        "orders": conn.execute("SELECT COUNT(*) AS n FROM orders").fetchone()["n"],
    }
