"""LangGraph orchestration: input_guard -> gather (observable LLM tool loop) ->
policy_eval (deterministic engine) -> act (verdict-gated write) -> respond ->
output_validation. The LLM bookends a deterministic core; money only moves on an
engine APPROVE, and the engine never sees chat text."""
from __future__ import annotations

import json

from langgraph.graph import END, START, StateGraph

from ..contracts import ClaimType, Decision, Verdict
from ..db import repository as repo
from ..policy.engine import evaluate
from . import guards
from .llm import FAIL_CLOSED_STOP_REASONS
from .prompts import gather_system, respond_system
from .state import AgentState, Classification
from .tools import TERMINAL_TOOL, ToolRegistry, TransientToolError

_GATHER_MAX_ROUNDS = 8

_RESPOND_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "verdict": {"type": "string", "enum": ["APPROVE", "DENY", "ESCALATE"]},
            "message": {"type": "string"},
        },
        "required": ["verdict", "message"],
        "additionalProperties": False,
    },
}


def _last_user_text(messages: list[dict]) -> str:
    for m in reversed(messages):
        if m.get("role") == "user":
            c = m.get("content")
            return c if isinstance(c, str) else json.dumps(c)
    return ""


def _escalate(reason: str) -> Verdict:
    return Verdict(decision=Decision.ESCALATE, reasons=[reason], policy_refs=["P-AMBIGUOUS"])


def _safe_message(verdict: Verdict) -> str:
    d = verdict.decision
    why = "; ".join(verdict.reasons) or "policy"
    if d is Decision.APPROVE:
        return "Your refund has been approved and will be processed."
    if d is Decision.ESCALATE:
        return "This request needs a human to review it — I've escalated it for you."
    return f"I'm sorry, but this refund can't be approved ({why})."


# --- nodes ---------------------------------------------------------------- #


def node_input_guard(state: AgentState) -> dict:
    cfg, deps, run_id = state["config"], state["deps"], state["run_id"]
    flagged = False
    if cfg.input_guard_enabled:
        with deps.recorder.step(run_id, "input_guard", "scan") as h:
            text = _last_user_text(state["messages"])
            h.set_input({"text": text[:200]})
            res = guards.scan_injection(text)
            h.set_output(res)
            flagged = res["flagged"]
    return {"guard_flagged": flagged}


def _dispatch_with_retry(tools: ToolRegistry, name: str, args: dict, handle, attempts: int = 2) -> dict:
    for i in range(attempts):
        try:
            return tools.dispatch(name, args)
        except TransientToolError as exc:
            handle.record_retry({"type": "TransientToolError", "message": str(exc)})
            if i == attempts - 1:
                raise
    return {}  # unreachable


def node_gather(state: AgentState) -> dict:
    cfg, deps, run_id, identity = state["config"], state["deps"], state["run_id"], state["identity"]
    tools = ToolRegistry(deps.conn, identity, fault_enabled=True)
    system = gather_system(cfg.persona, identity)
    messages = list(state["messages"])

    for _ in range(_GATHER_MAX_ROUNDS):
        with deps.recorder.step(run_id, "llm", "gather") as h:
            h.set_input({"messages": len(messages)})
            result = deps.llm.create(system=system, messages=messages, config=cfg, tools=tools.schemas())
            for attempt in result.attempts:
                h.record_retry(attempt.get("error", attempt))
            h.set_usage(result.input_tokens, result.output_tokens, result.cache_read_tokens)
            h.set_output({
                "stop_reason": result.stop_reason,
                "tools": [c["name"] for c in result.tool_calls],
                "text": result.text[:200],
            })

        if result.stop_reason in FAIL_CLOSED_STOP_REASONS:
            return {"verdict": _escalate("agent could not complete safely"),
                    "reply": "This request needs a human to review it — I've escalated it.",
                    "outcome": "ESCALATE"}

        if result.stop_reason != "tool_use":
            return {"reply": result.text or "Could you share your order id and what went wrong?",
                    "outcome": "INFO"}

        classification = None
        tool_results = []
        for call in result.tool_calls:
            with deps.recorder.step(run_id, "tool", call["name"]) as h:
                h.set_input(call["input"])
                out = _dispatch_with_retry(tools, call["name"], call["input"], h)
                h.set_output(out)
            tool_results.append({"type": "tool_result", "tool_use_id": call["id"], "content": json.dumps(out)})
            if call["name"] == TERMINAL_TOOL:
                classification = Classification(
                    order_id=call["input"]["order_id"],
                    claim_type=ClaimType(call["input"]["claim_type"]),
                    confidence=float(call["input"]["confidence"]),
                )
        messages.append({"role": "assistant", "content": result.raw_content or ""})
        messages.append({"role": "user", "content": tool_results})
        if classification is not None:
            return {"classification": classification}

    return {"verdict": _escalate("could not gather enough information"),
            "reply": "This request needs a human to review it — I've escalated it.",
            "outcome": "ESCALATE"}


def node_policy_eval(state: AgentState) -> dict:
    deps, run_id, identity = state["deps"], state["run_id"], state["identity"]
    cl: Classification = state["classification"]
    with deps.recorder.step(run_id, "policy_engine", "evaluate") as h:
        ctx = repo.build_refund_context(
            deps.conn, cl.order_id, identity.customer_id,
            claim_type=cl.claim_type, claim_confidence=cl.confidence, now=deps.now,
        )
        if ctx is None:
            h.set_input({"order_id": cl.order_id})
            h.set_output({"error": "order_not_found_for_customer"})
            return {"reply": "I couldn't find that order on your account.", "outcome": "NOT_FOUND"}
        verdict = evaluate(ctx)
        h.set_input({"order_id": ctx.order_id, "status": ctx.order_status.value,
                     "amount": ctx.refund_amount, "claim": ctx.claim_type.value})
        h.set_output({"decision": verdict.decision.value, "policy_refs": verdict.policy_refs})
    return {"refund_context": ctx, "verdict": verdict}


def node_act(state: AgentState) -> dict:
    deps, run_id = state["deps"], state["run_id"]
    verdict: Verdict = state["verdict"]
    ctx = state.get("refund_context")
    refund_id = None
    with deps.recorder.step(run_id, "action", verdict.decision.value) as h:
        h.set_input({"decision": verdict.decision.value})
        if verdict.decision is Decision.APPROVE and ctx is not None:
            try:
                repo.process_refund(deps.conn, ctx.order_id, ctx.customer_id, verdict.refund_amount, deps.now)
                repo.log_verdict(deps.conn, verdict=verdict, order_id=ctx.order_id,
                                 customer_id=ctx.customer_id, now=deps.now, executed=True)
                refund_id = ctx.order_id
                h.set_output({"refunded": True, "amount": verdict.refund_amount})
            except repo.AlreadyRefundedError:
                h.set_output({"error": "already_refunded"})
                return {"outcome": "ERROR"}
        else:
            if ctx is not None:
                repo.log_verdict(deps.conn, verdict=verdict, order_id=ctx.order_id,
                                 customer_id=ctx.customer_id, now=deps.now, executed=False)
            h.set_output({"refunded": False})
    return {"refund_id": refund_id, "outcome": verdict.decision.value}


def node_respond(state: AgentState) -> dict:
    cfg, deps, run_id, identity = state["config"], state["deps"], state["run_id"], state["identity"]
    verdict: Verdict = state["verdict"]
    system = respond_system(cfg.persona, verdict, identity)
    with deps.recorder.step(run_id, "llm", "respond") as h:
        h.set_input({"decision": verdict.decision.value})
        result = deps.llm.create(
            system=system,
            messages=[{"role": "user", "content": "Please communicate the decision to the customer."}],
            config=cfg, force_json=_RESPOND_SCHEMA,
        )
        for attempt in result.attempts:
            h.record_retry(attempt.get("error", attempt))
        h.set_usage(result.input_tokens, result.output_tokens, result.cache_read_tokens)
        try:
            parsed = json.loads(result.text)
            communicated, reply = parsed.get("verdict"), parsed.get("message", "")
        except (json.JSONDecodeError, TypeError):
            communicated, reply = None, result.text
        h.set_output({"communicated": communicated, "message": reply[:200]})
    return {"reply": reply, "communicated_verdict": communicated}


def node_output_validation(state: AgentState) -> dict:
    cfg, deps, run_id = state["config"], state["deps"], state["run_id"]
    if not cfg.output_validation_enabled:
        return {}
    verdict: Verdict = state["verdict"]
    engine_dec = verdict.decision.value
    with deps.recorder.step(run_id, "output_validation", "verdict_match") as h:
        communicated = state.get("communicated_verdict")
        h.set_input({"communicated": communicated, "engine": engine_dec})
        if not guards.verdicts_match(communicated, engine_dec):
            h.set_output({"ok": False, "action": "repaired"})
            return {"reply": _safe_message(verdict), "communicated_verdict": engine_dec}
        h.set_output({"ok": True})
    return {}


# --- routing + build ------------------------------------------------------ #


def _route_after_gather(state: AgentState) -> str:
    return "classified" if state.get("classification") is not None else "end"


def _route_after_policy_eval(state: AgentState) -> str:
    return "act" if state.get("verdict") is not None else "end"


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("input_guard", node_input_guard)
    g.add_node("gather", node_gather)
    g.add_node("policy_eval", node_policy_eval)
    g.add_node("act", node_act)
    g.add_node("respond", node_respond)
    g.add_node("output_validation", node_output_validation)

    g.add_edge(START, "input_guard")
    g.add_edge("input_guard", "gather")
    g.add_conditional_edges("gather", _route_after_gather, {"classified": "policy_eval", "end": END})
    g.add_conditional_edges("policy_eval", _route_after_policy_eval, {"act": "act", "end": END})
    g.add_edge("act", "respond")
    g.add_edge("respond", "output_validation")
    g.add_edge("output_validation", END)
    return g.compile()


graph = build_graph()
