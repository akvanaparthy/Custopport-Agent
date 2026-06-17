"""The single entrypoint the API layer calls. Pure orchestration — no FastAPI
imports. Builds effective config + trace recorder, runs the compiled graph, and
returns a typed result."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from ..contracts import Verdict
from ..observability.trace_recorder import TraceRecorder
from ..settings.store import get_effective_config
from .graph import graph
from .llm import LLM
from .state import AgentState, IdentityContext


@dataclass
class Deps:
    conn: Any
    llm: LLM
    recorder: TraceRecorder
    now: datetime


@dataclass
class AgentRunResult:
    run_id: str
    outcome: str
    reply: str
    verdict: Optional[Verdict]
    refund_id: Optional[str]


def run_agent(
    *,
    messages: list[dict],
    identity: IdentityContext,
    conn: Any,
    llm: LLM,
    conversation_id: str,
    message_id: str,
    now: Optional[datetime] = None,
) -> AgentRunResult:
    now = now or datetime.now(timezone.utc)
    config = get_effective_config(conn)
    recorder = TraceRecorder(conn)
    run_id = recorder.start_run(
        conversation_id=conversation_id,
        message_id=message_id,
        identity_mode=identity.mode.value,
        customer_id=identity.customer_id,
        model=config.model,
    )
    deps = Deps(conn=conn, llm=llm, recorder=recorder, now=now)
    state: AgentState = {
        "messages": messages,
        "identity": identity,
        "config": config,
        "run_id": run_id,
        "deps": deps,
    }
    final = graph.invoke(state)

    verdict: Optional[Verdict] = final.get("verdict")
    outcome = final.get("outcome") or (verdict.decision.value if verdict else "INFO")
    recorder.finish_run(run_id, final_verdict=verdict.decision.value if verdict else None, status="completed")
    return AgentRunResult(
        run_id=run_id,
        outcome=outcome,
        reply=final.get("reply", ""),
        verdict=verdict,
        refund_id=final.get("refund_id"),
    )
