"""Single source of truth for token cost. Consumed by the trace recorder (and,
mirrored, by the frontend) so every layer reports the SAME USD.

Cache reads are billed at ~0.1x input; cache writes at ~1.25x input (per the
claude-api facts). Prices come from contracts.MODEL_PRICING ($/1M in,out)."""
from __future__ import annotations

import logging

from ..contracts import MODEL_PRICING

logger = logging.getLogger(__name__)

CACHE_READ_MULTIPLIER = 0.1
CACHE_WRITE_MULTIPLIER = 1.25


def cost_usd(
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float:
    """USD cost for one model call's token usage. Unknown model -> 0.0 (logged)."""
    prices = MODEL_PRICING.get(model)
    if prices is None:
        logger.warning("no price for model %r; cost reported as 0.0", model)
        return 0.0
    in_price, out_price = prices
    total = (
        input_tokens * in_price
        + output_tokens * out_price
        + cache_read_tokens * in_price * CACHE_READ_MULTIPLIER
        + cache_write_tokens * in_price * CACHE_WRITE_MULTIPLIER
    )
    return total / 1_000_000
