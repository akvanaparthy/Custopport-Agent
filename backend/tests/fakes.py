"""A scriptable fake LLM for orchestration tests (no API key, deterministic)."""
from __future__ import annotations

import json
import re

from app.agent.llm import LLMResult

_DECISION_RE = re.compile(r"\[decision\]\s+(\w+)")


def classify(order_id: str, claim_type: str, confidence: float = 0.95) -> dict:
    return {"name": "classify_claim", "input": {"order_id": order_id, "claim_type": claim_type, "confidence": confidence}}


def get_order(order_id: str) -> dict:
    return {"name": "get_order", "input": {"order_id": order_id}}


class FakeLLM:
    """gather_rounds: list of rounds; each round is a list of tool calls returned
    on that gather turn. respond_decision: if set, the respond turn returns this
    verdict (a 'liar' to exercise output-validation); otherwise it honestly echoes
    the engine decision found in the respond system prompt."""

    def __init__(self, gather_rounds, respond_decision: str | None = None):
        self._rounds = [list(r) for r in gather_rounds]
        self._i = 0
        self._respond_decision = respond_decision

    def create(self, *, system, messages, config, tools=None, force_json=None) -> LLMResult:
        if tools is not None:  # gather turn
            calls = self._rounds[self._i] if self._i < len(self._rounds) else []
            self._i += 1
            tool_calls = [
                {"id": f"t{self._i}_{j}", "name": c["name"], "input": c["input"]}
                for j, c in enumerate(calls)
            ]
            return LLMResult(
                stop_reason="tool_use" if tool_calls else "end_turn",
                tool_calls=tool_calls, raw_content=[], input_tokens=50, output_tokens=10,
            )
        # respond turn
        decision = self._respond_decision
        if decision is None:
            m = _DECISION_RE.search(system)
            decision = m.group(1) if m else "ESCALATE"
        return LLMResult(
            text=json.dumps({"verdict": decision, "message": f"Decision: {decision}."}),
            stop_reason="end_turn", input_tokens=80, output_tokens=20,
        )
