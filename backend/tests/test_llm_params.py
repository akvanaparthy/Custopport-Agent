"""Tier-1: the LLM request mapping. The load-bearing guarantee is that we never
send sampling params (they 400 on Opus 4.8) and use effort as the dial."""
from __future__ import annotations

from app.agent.llm import build_request_params
from app.contracts import AgentSettings, Effort


def test_never_sends_sampling_params():
    p = build_request_params(AgentSettings(), "sys", [{"role": "user", "content": "hi"}])
    assert "temperature" not in p
    assert "top_p" not in p
    assert "top_k" not in p


def test_effort_and_model_from_config():
    p = build_request_params(AgentSettings(), "sys", [])
    assert p["model"] == "claude-sonnet-4-6"
    assert p["max_tokens"] == 4096
    assert p["output_config"]["effort"] == "medium"
    assert "thinking" not in p  # adaptive off by default


def test_adaptive_thinking_only_when_enabled():
    p = build_request_params(AgentSettings(adaptive_thinking=True, effort=Effort.HIGH), "sys", [])
    assert p["thinking"] == {"type": "adaptive", "display": "summarized"}
    assert p["output_config"]["effort"] == "high"


def test_tools_and_forced_json():
    p = build_request_params(
        AgentSettings(), "sys", [], tools=[{"name": "t"}],
        force_json={"type": "json_schema", "schema": {}},
    )
    assert p["tools"] == [{"name": "t"}]
    assert p["output_config"]["format"] == {"type": "json_schema", "schema": {}}
