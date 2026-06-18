"""Frozen cross-subsystem contracts.

This is the single source of truth for types shared across the policy engine,
orchestration, identity, observability, settings, the API layer, and (mirrored)
the frontend. Freezing these here is what makes "zero config errors" achievable:
every subsystem imports the same enums, the same field names, and the same
canonical settings keys.

Nothing in this module reads a clock, a database, or the network. The policy
engine depends only on this module and stays pure.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #


class Decision(str, Enum):
    APPROVE = "APPROVE"
    DENY = "DENY"
    ESCALATE = "ESCALATE"


class ClaimType(str, Enum):
    DAMAGED = "damaged"
    DEFECTIVE = "defective"
    NOT_AS_DESCRIBED = "not_as_described"
    WRONG_ITEM = "wrong_item"
    CHANGED_MIND = "changed_mind"
    OTHER = "other"
    UNKNOWN = "unknown"


class OrderStatus(str, Enum):
    DELIVERED = "delivered"
    SHIPPED = "shipped"
    PROCESSING = "processing"
    PENDING = "pending"
    CANCELLED = "cancelled"


class ItemCondition(str, Enum):
    """The condition of the item *being returned*, recorded with the return
    request (an RMA field) — not the seller asserting a fault. The engine only
    distinguishes opened/used (a non-defect return of an opened item needs a
    human) from the rest; see engine `_ESCALATE_CONDITIONS`."""

    NEW = "new"
    DAMAGED = "damaged"
    DEFECTIVE = "defective"
    USED = "used"
    OPENED = "opened"


class IdentityMode(str, Enum):
    AUTHENTICATED = "authenticated"
    IN_CHAT = "in_chat"


class Effort(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    MAX = "max"


class StepType(str, Enum):
    """Canonical trace step enum — also the DB CHECK constraint and the
    frontend StepType. Internal orchestration events map onto these; a retry
    folds into the owning step row (retry_count + attempts_json)."""

    INPUT_GUARD = "input_guard"
    LLM = "llm"
    TOOL = "tool"
    POLICY_ENGINE = "policy_engine"
    ACTION = "action"
    OUTPUT_VALIDATION = "output_validation"


# Categories that are never refundable (mirrors P-CATEGORY in policy.md).
NON_REFUNDABLE_CATEGORIES = frozenset({"gift_card", "digital", "perishable"})

# Reasons that clearly justify a refund within the window (P-CLEAN-APPROVE).
APPROVABLE_CLAIMS = frozenset(
    {
        ClaimType.DAMAGED,
        ClaimType.DEFECTIVE,
        ClaimType.NOT_AS_DESCRIBED,
        ClaimType.WRONG_ITEM,
    }
)


# --------------------------------------------------------------------------- #
# Policy engine I/O — frozen field sets
# --------------------------------------------------------------------------- #


class RefundContext(BaseModel):
    """Structured facts the deterministic engine reads. NEVER contains raw chat
    text. `days_since_delivery` is computed upstream from an injected `now`, so
    the engine itself reads no clock."""

    order_id: str
    customer_id: str
    order_status: OrderStatus
    days_since_delivery: Optional[int] = None
    order_total: float = 0.0
    refund_amount: float = 0.0
    is_final_sale: bool = False
    already_refunded: bool = False
    category: str = "general"
    claim_type: ClaimType = ClaimType.UNKNOWN
    claim_confidence: float = 0.0
    item_condition: Optional[ItemCondition] = None  # declared return condition (see ItemCondition)

    @property
    def non_refundable_category(self) -> bool:
        return self.category in NON_REFUNDABLE_CATEGORIES


class Verdict(BaseModel):
    """The engine's decision. `auto_executable` is True only for APPROVE; the
    `act` node refuses to write money on anything else."""

    decision: Decision
    reasons: list[str] = Field(default_factory=list)
    policy_refs: list[str] = Field(default_factory=list)
    auto_executable: bool = False
    refund_amount: float = 0.0


# --------------------------------------------------------------------------- #
# Settings — one canonical key set
# --------------------------------------------------------------------------- #

# Hard cap for the max_tokens validator. Non-streaming requests above this risk
# the SDK's ~10-minute ValueError guard; the LLM calls here are non-streaming.
MAX_TOKENS_CEILING = 16000

# Supported model IDs (exact strings — no date suffixes).
SUPPORTED_MODELS = ("claude-sonnet-4-6", "claude-opus-4-8", "claude-haiku-4-5")

# Per-model pricing in USD per 1M tokens: (input, output). cache_read = 0.1x
# input, cache_write = 1.25x input — applied in observability/pricing.py.
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-haiku-4-5": (1.0, 5.0),
}


class AgentSettings(BaseModel):
    """The effective, runtime-tunable config the agent reads per request.

    Canonical keys only. `.env` seeds defaults (default_model->model,
    default_effort->effort, max_output_tokens->max_tokens); the admin Settings
    page overrides them in SQLite. The agent reads `max_tokens` (not
    `max_output_tokens`)."""

    model_config = ConfigDict(protected_namespaces=())

    model: str = "claude-sonnet-4-6"
    effort: Effort = Effort.MEDIUM
    adaptive_thinking: bool = False
    max_tokens: int = 4096
    input_guard_enabled: bool = True
    output_validation_enabled: bool = True
    identity_mode: IdentityMode = IdentityMode.AUTHENTICATED
    persona: str = (
        "You are a calm, professional e-commerce customer-support agent. You "
        "help customers with refund requests. You never decide refunds "
        "yourself — a policy engine does — you only gather facts and explain "
        "the outcome clearly and kindly."
    )


# Canonical settings keys, in one place, for the store + admin API to validate.
SETTINGS_KEYS = tuple(AgentSettings.model_fields.keys())


# --------------------------------------------------------------------------- #
# SSE status event names (backend -> browser; NOT the Anthropic token stream)
# --------------------------------------------------------------------------- #


class SSEEvent(str, Enum):
    RUN_STARTED = "run_started"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    VERDICT = "verdict"
    FINAL_MESSAGE = "final_message"
    DONE = "done"
    ERROR = "error"
