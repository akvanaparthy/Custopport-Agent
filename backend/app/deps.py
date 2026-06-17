"""FastAPI dependencies. A request-scoped SQLite connection to the configured DB
(one connection per request — simplest correct choice for SQLite under WAL)."""
from __future__ import annotations

from typing import Iterator

from fastapi import HTTPException

from .config import get_settings
from .db.database import connect


def get_conn() -> Iterator:
    conn = connect(get_settings().db_path)
    try:
        yield conn
    finally:
        conn.close()


def get_llm():
    """Live Anthropic-backed LLM. Fails fast with a friendly message if the key
    is missing (it's only needed for actual chat turns, not the build/tests)."""
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY not set — add it to backend/.env to use the chat agent.",
        )
    import anthropic

    from .agent import AnthropicLLM

    return AnthropicLLM(anthropic.Anthropic(api_key=settings.anthropic_api_key))
