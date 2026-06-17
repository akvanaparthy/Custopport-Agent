"""Tier-1: token cost is computed identically everywhere."""
from __future__ import annotations

from app.observability.pricing import cost_usd


def test_opus_input_output():
    # opus-4-8 = $5 in / $25 out per 1M
    assert cost_usd("claude-opus-4-8", 1_000_000, 1_000_000) == 30.0


def test_sonnet_pricing():
    assert cost_usd("claude-sonnet-4-6", 1_000_000, 0) == 3.0
    assert cost_usd("claude-sonnet-4-6", 0, 1_000_000) == 15.0


def test_cache_read_is_tenth_of_input():
    # 1M cache-read on opus = 0.1 * $5 = $0.50
    assert cost_usd("claude-opus-4-8", cache_read_tokens=1_000_000) == 0.5


def test_cache_write_is_1_25x_input():
    assert cost_usd("claude-opus-4-8", cache_write_tokens=1_000_000) == 6.25


def test_unknown_model_is_zero():
    assert cost_usd("gpt-4", 1_000_000, 1_000_000) == 0.0
