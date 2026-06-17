"""LLM boundary. `build_request_params` is the pure, tested core that maps our
config to the Anthropic request — crucially it NEVER sends temperature/top_p/top_k
(they 400 on Opus 4.8), uses `effort` as the reasoning dial, and only sets
adaptive thinking when the toggle is on. `AnthropicLLM` is the live impl; the
orchestration depends on the `LLM` protocol so tests inject a fake (no key)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

from ..contracts import AgentSettings


@dataclass
class LLMResult:
    text: str = ""
    tool_calls: list[dict] = field(default_factory=list)  # [{id, name, input}]
    stop_reason: str = "end_turn"
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    attempts: list[dict] = field(default_factory=list)
    raw_content: Any = None  # assistant content blocks, for message history


class LLM(Protocol):
    def create(
        self,
        *,
        system: str,
        messages: list[dict],
        config: AgentSettings,
        tools: Optional[list[dict]] = None,
        force_json: Optional[dict] = None,
    ) -> LLMResult: ...


def build_request_params(
    config: AgentSettings,
    system: str,
    messages: list[dict],
    tools: Optional[list[dict]] = None,
    force_json: Optional[dict] = None,
) -> dict:
    """Pure mapping from our config to anthropic.messages.create kwargs.
    No sampling params, ever."""
    output_config: dict = {"effort": config.effort.value}
    if force_json is not None:
        output_config["format"] = force_json
    params: dict = {
        "model": config.model,
        "max_tokens": config.max_tokens,
        "system": system,
        "messages": messages,
        "output_config": output_config,
    }
    if tools:
        params["tools"] = tools
    if config.adaptive_thinking:
        params["thinking"] = {"type": "adaptive", "display": "summarized"}
    return params


# stop reasons that must fail closed (never proceed on partial facts)
FAIL_CLOSED_STOP_REASONS = {"max_tokens", "model_context_window_exceeded", "refusal", "pause_turn"}


class AnthropicLLM:
    """Live Anthropic client. Retries rate-limit/5xx with backoff (recording each
    attempt). Not unit-tested without a key — `build_request_params` carries the
    tested logic; orchestration tests use a fake LLM."""

    def __init__(self, client: Any, max_retries: int = 2):
        self._client = client
        self._max_retries = max_retries

    def create(self, *, system, messages, config, tools=None, force_json=None) -> LLMResult:
        import anthropic

        params = build_request_params(config, system, messages, tools, force_json)
        attempts: list[dict] = []
        start = time.perf_counter()
        for attempt in range(self._max_retries + 1):
            try:
                resp = self._client.messages.create(**params)
                break
            except (anthropic.RateLimitError, anthropic.InternalServerError) as exc:
                attempts.append({"attempt": attempt + 1, "status": "error", "error": {"type": type(exc).__name__, "message": str(exc)[:200]}})
                if attempt == self._max_retries:
                    raise
                time.sleep(min(2 ** attempt, 8))
        return self._to_result(resp, attempts)

    @staticmethod
    def _to_result(resp: Any, attempts: list[dict]) -> LLMResult:
        text_parts, tool_calls = [], []
        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append({"id": block.id, "name": block.name, "input": block.input})
        usage = resp.usage
        return LLMResult(
            text="".join(text_parts),
            tool_calls=tool_calls,
            stop_reason=resp.stop_reason,
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
            attempts=attempts,
            raw_content=resp.content,
        )
