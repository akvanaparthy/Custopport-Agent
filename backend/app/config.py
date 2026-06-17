"""Boot/infra config from `.env` (pydantic-settings). Seeds the runtime-settings
defaults; the live, admin-tunable overrides live in the SQLite settings row
(see settings/store.py). Only ANTHROPIC_API_KEY matters at agent runtime — it's
optional here so the app (and tests) import without it; the API layer fails fast
with a friendly message if it's missing when a live run is attempted."""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

from .contracts import Effort, IdentityMode

_DEFAULT_PERSONA = (
    "You are a calm, professional e-commerce customer-support agent. You help "
    "customers with refund requests. You never decide refunds yourself — a policy "
    "engine does — you only gather facts and explain the outcome clearly and kindly."
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", protected_namespaces=())

    anthropic_api_key: Optional[str] = None
    db_path: str = "./data/app.db"

    # Seeds for the runtime settings row (mapped to canonical keys in the store).
    default_model: str = "claude-sonnet-4-6"
    default_effort: Effort = Effort.MEDIUM
    adaptive_thinking: bool = False
    max_output_tokens: int = 4096
    input_guard_enabled: bool = True
    output_validation_enabled: bool = True
    identity_mode: IdentityMode = IdentityMode.AUTHENTICATED
    persona: str = _DEFAULT_PERSONA

    # CORS for the optional split deploy; same-origin local needs none.
    allowed_origins: list[str] = ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
