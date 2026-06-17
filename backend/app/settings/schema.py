"""Settings API schema. SettingsUpdate is a partial (any subset) with strict
validation and `extra='forbid'` — so a stray `temperature`/`top_p`/`top_k`
(rejected by Sonnet 4.6 / Opus 4.8) is a 422, not a silent runtime 400. The
effective config the agent reads is `contracts.AgentSettings`."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..contracts import MAX_TOKENS_CEILING, SUPPORTED_MODELS, AgentSettings, Effort, IdentityMode


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    model: Optional[str] = None
    effort: Optional[Effort] = None
    adaptive_thinking: Optional[bool] = None
    max_tokens: Optional[int] = Field(default=None, ge=1, le=MAX_TOKENS_CEILING)
    input_guard_enabled: Optional[bool] = None
    output_validation_enabled: Optional[bool] = None
    identity_mode: Optional[IdentityMode] = None
    persona: Optional[str] = None

    @field_validator("model")
    @classmethod
    def _supported_model(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in SUPPORTED_MODELS:
            raise ValueError(f"model must be one of {SUPPORTED_MODELS}")
        return v


class SettingsView(AgentSettings):
    """Effective config returned to the admin UI, plus where each value came from."""

    model_config = ConfigDict(protected_namespaces=())
    source_map: dict[str, str] = {}
