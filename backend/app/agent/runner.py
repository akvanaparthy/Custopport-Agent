"""The single entrypoint the API layer calls. Pure orchestration — no FastAPI
imports. Builds effective config + trace recorder, runs the compiled graph, and
returns a typed result."""
from __future__ import annotations

from dataclasses import dataclass, field
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
    progress: list[str] = field(default_factory=list)  # gather-phase notes for the UI


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
    try:
        final = graph.invoke(state)
    except Exception:
        # Fail closed: an LLM/DB/infra failure mid-run never approves and never
        # leaves the trace dangling. Finalize the run as errored (so the console
        # shows it) and hand the caller a graceful message.
        recorder.finish_run(run_id, final_verdict=None, status="error")
        return AgentRunResult(
            run_id=run_id, outcome="ERROR", verdict=None, refund_id=None,
            reply="I'm sorry — something went wrong on our end and I couldn't complete that "
                  "request. Please try again in a moment.",
        )

    verdict: Optional[Verdict] = final.get("verdict")
    outcome = final.get("outcome") or (verdict.decision.value if verdict else "INFO")
    recorder.finish_run(run_id, final_verdict=verdict.decision.value if verdict else None, status="completed")
    return AgentRunResult(
        run_id=run_id,
        outcome=outcome,
        reply=final.get("reply", ""),
        verdict=verdict,
        refund_id=final.get("refund_id"),
        progress=final.get("progress") or [],
    )
