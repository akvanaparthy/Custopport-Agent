"""Orchestration state threaded through the graph. Domain types (RefundContext,
Verdict, ClaimType) come from contracts; this adds only orchestration-specific
shapes. The graph never puts raw chat text into the engine — only structured
facts + the LLM's claim classification."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, TypedDict

from ..contracts import AgentSettings, ClaimType, IdentityMode, RefundContext, Verdict


@dataclass
class IdentityContext:
    """Who the agent is acting for. In authenticated mode customer_id is trusted
    from the server-side session; in in_chat mode it's set only after a
    deterministic ownership check (built out in the identity step)."""

    mode: IdentityMode
    customer_id: Optional[str] = None
    claimed_email: Optional[str] = None
    claimed_order_id: Optional[str] = None
    verified: bool = False


@dataclass
class Classification:
    """The LLM's structured read of the request — feeds the engine, never decides."""

    order_id: str
    claim_type: ClaimType
    confidence: float


class AgentState(TypedDict, total=False):
    # inputs
    messages: list[dict]
    identity: IdentityContext
    config: AgentSettings
    run_id: str
    deps: Any  # Deps bundle (conn, llm, tools, recorder) — see runner.py
    # working values
    guard_flagged: bool
    progress: list[str]  # gather-phase "let me check…" notes, surfaced to the user
    classification: Optional[Classification]
    refund_context: Optional[RefundContext]
    verdict: Optional[Verdict]
    communicated_verdict: Optional[str]
    reply: str
    refund_id: Optional[str]
    outcome: str  # APPROVE | DENY | ESCALATE | NOT_FOUND | INFO | BLOCKED | ERROR
