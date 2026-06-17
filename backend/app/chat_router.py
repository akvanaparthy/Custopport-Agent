"""Customer-facing chat + session endpoints. The session is the identity
transport: create one (authenticated -> bound to a customer; in_chat -> verify
first), then chat. /api/chat streams coarse SSE status events while run_agent
does the work; the per-step live trace is on the admin SSE stream."""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .agent.runner import run_agent
from .contracts import NON_REFUNDABLE_CATEGORIES, IdentityMode
from .db import repository as repo
from .deps import get_conn, get_llm
from .identity import session as sessions
from .policy.policy_config import AUTO_APPROVE_CEILING, RETURN_WINDOW_DAYS

router = APIRouter(prefix="/api", tags=["chat"])


class CreateSessionBody(BaseModel):
    identity_mode: IdentityMode = IdentityMode.AUTHENTICATED
    customer_id: Optional[str] = None


class VerifyBody(BaseModel):
    email: str
    order_id: str


class ChatBody(BaseModel):
    message: str
    conversation_id: Optional[str] = None


@router.get("/customers")
def list_customers(conn=Depends(get_conn)):
    """The 15 seeded customers — powers the authenticated-mode switcher."""
    return [
        {"customer_id": r["customer_id"], "name": r["name"], "email": r["email"]}
        for r in repo.list_customers(conn)
    ]


@router.post("/session")
def create_session(body: CreateSessionBody, conn=Depends(get_conn)):
    try:
        return sessions.create_session(conn, identity_mode=body.identity_mode, customer_id=body.customer_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/session")
def current_session(x_session_id: str = Header(...), conn=Depends(get_conn)):
    sess = sessions.get_session(conn, x_session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="session not found")
    return sess


@router.post("/session/verify")
def verify_session(body: VerifyBody, x_session_id: str = Header(...), conn=Depends(get_conn)):
    sess = sessions.verify_in_chat(conn, x_session_id, body.email, body.order_id)
    if sess is None:
        raise HTTPException(status_code=400, detail="verification failed")
    return sess


def _verified_customer(conn, session_id: str) -> str:
    sess = sessions.get_session(conn, session_id)
    if sess is None:
        raise HTTPException(status_code=401, detail="no session")
    if not sess["verified"] or not sess["customer_id"]:
        raise HTTPException(status_code=403, detail="session not verified")
    return sess["customer_id"]


def _order_hint(row, now: datetime) -> dict:
    """A read-only eligibility preview from the hard rules (claim-independent).
    Not the verdict — the actual decision still depends on the claim + condition."""
    if row["already_refunded"]:
        return {"tone": "refunded", "label": "Already refunded"}
    if row["is_final_sale"]:
        return {"tone": "blocked", "label": "Final sale — not refundable"}
    if row["category"] in NON_REFUNDABLE_CATEGORIES:
        return {"tone": "blocked", "label": "Not refundable (category)"}
    if row["status"] != "delivered":
        return {"tone": "blocked", "label": f"Not yet delivered ({row['status']})"}
    if row["delivered_date"]:
        days = (now.date() - date.fromisoformat(row["delivered_date"][:10])).days
        if days > RETURN_WINDOW_DAYS:
            return {"tone": "blocked", "label": "Return window closed"}
    if row["order_total"] > AUTO_APPROVE_CEILING:
        return {"tone": "review", "label": "Eligible — needs human review"}
    return {"tone": "eligible", "label": "Likely eligible for a refund"}


def _order_payload(row, now: datetime) -> dict:
    return {
        "order_id": row["order_id"],
        "item_name": row["item_name"],
        "category": row["category"],
        "order_total": row["order_total"],
        "currency": row["currency"],
        "status": row["status"],
        "order_date": row["order_date"],
        "delivered_date": row["delivered_date"],
        "is_final_sale": bool(row["is_final_sale"]),
        "item_condition": row["item_condition"],
        "already_refunded": bool(row["already_refunded"]),
        "refunded_amount": row["refunded_amount"],
        "hint": _order_hint(row, now),
    }


@router.get("/orders")
def my_orders(x_session_id: str = Header(...), conn=Depends(get_conn)):
    cid = _verified_customer(conn, x_session_id)
    now = datetime.now(timezone.utc)
    return [_order_payload(o, now) for o in repo.list_orders(conn, cid)]


@router.get("/orders/{order_id}")
def my_order(order_id: str, x_session_id: str = Header(...), conn=Depends(get_conn)):
    cid = _verified_customer(conn, x_session_id)
    row = repo.get_order(conn, order_id, cid)
    if row is None:
        raise HTTPException(status_code=404, detail="order not found")
    return _order_payload(row, datetime.now(timezone.utc))


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/chat")
def chat(body: ChatBody, x_session_id: str = Header(...), conn=Depends(get_conn), llm=Depends(get_llm)):
    sess = sessions.get_session(conn, x_session_id)
    if sess is None:
        raise HTTPException(status_code=401, detail="no session")
    if not sess["verified"] or not sess["customer_id"]:
        raise HTTPException(status_code=403, detail="session not verified")

    identity = sessions.to_identity(sess)
    conversation_id = body.conversation_id or ("conv_" + uuid.uuid4().hex[:12])
    message_id = "msg_" + uuid.uuid4().hex[:12]

    def gen():
        yield _sse("run_started", {"conversation_id": conversation_id})
        result = run_agent(
            messages=[{"role": "user", "content": body.message}],
            identity=identity, conn=conn, llm=llm,
            conversation_id=conversation_id, message_id=message_id,
        )
        if result.verdict is not None:
            yield _sse("verdict", {
                "decision": result.verdict.decision.value,
                "policy_refs": result.verdict.policy_refs,
            })
        yield _sse("final_message", {
            "message": result.reply,
            "outcome": result.outcome,
            "run_id": result.run_id,
            "conversation_id": conversation_id,
        })
        yield _sse("done", {})

    return StreamingResponse(gen(), media_type="text/event-stream")
