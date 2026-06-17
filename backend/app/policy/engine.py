"""The deterministic refund policy engine.

This is the ONLY component that decides APPROVE / DENY / ESCALATE. It is a pure
function of a `RefundContext` (structured facts) — it never reads chat text, a
clock, a database, or the network. That purity is what makes the agent
injection-proof: no amount of clever phrasing can change a verdict, because the
phrasing never reaches this function.

Precedence (mirrors policy.md): **hard-DENY > ESCALATE > APPROVE**. We collect
every matching rule within the highest-priority tier that fires, so the trace
shows all the reasons at the deciding level (e.g. a final-sale item that is also
over $500 is DENIED on final-sale, never softened to an escalation).
"""
from __future__ import annotations

from ..contracts import (
    APPROVABLE_CLAIMS,
    ClaimType,
    Decision,
    ItemCondition,
    OrderStatus,
    RefundContext,
    Verdict,
)
from .policy_config import (
    AUTO_APPROVE_CEILING,
    CLASSIFY_CONFIDENCE_THRESHOLD,
    POLICY_REFS,
    RETURN_WINDOW_DAYS,
)

_ESCALATE_CONDITIONS = (ItemCondition.USED, ItemCondition.OPENED)
_DEFECT_CLAIMS = (ClaimType.DAMAGED, ClaimType.DEFECTIVE)


def _hard_denies(ctx: RefundContext) -> list[str]:
    """Hard-deny rules. Any match means the refund is refused outright."""
    hits: list[str] = []
    if ctx.already_refunded:
        hits.append("P-ALREADY-REFUNDED")
    if ctx.is_final_sale:
        hits.append("P-FINAL-SALE")
    if ctx.non_refundable_category:
        hits.append("P-CATEGORY")
    if ctx.order_status != OrderStatus.DELIVERED:
        hits.append("P-STATUS")
    if ctx.days_since_delivery is not None and ctx.days_since_delivery > RETURN_WINDOW_DAYS:
        hits.append("P-WINDOW")
    return hits


def _escalations(ctx: RefundContext) -> list[str]:
    """Escalation rules. Reached only when no hard-deny fired."""
    hits: list[str] = []
    if ctx.refund_amount > AUTO_APPROVE_CEILING:
        hits.append("P-MAX-AUTO")
    if ctx.item_condition in _ESCALATE_CONDITIONS and ctx.claim_type not in _DEFECT_CLAIMS:
        hits.append("P-CONDITION")
    # Unclassifiable / low-confidence / non-standard (e.g. change-of-mind) claims
    # are sent to a human rather than guessed. Also: a delivered order with an
    # unknown delivery date can't be window-checked, so escalate for safety.
    ambiguous = (
        ctx.claim_type not in APPROVABLE_CLAIMS
        or ctx.claim_confidence < CLASSIFY_CONFIDENCE_THRESHOLD
        or (ctx.order_status == OrderStatus.DELIVERED and ctx.days_since_delivery is None)
    )
    if ambiguous:
        hits.append("P-AMBIGUOUS")
    return hits


def _verdict(decision: Decision, refs: list[str], *, refund_amount: float) -> Verdict:
    return Verdict(
        decision=decision,
        policy_refs=refs,
        reasons=[POLICY_REFS[r] for r in refs],
        auto_executable=(decision is Decision.APPROVE),
        refund_amount=refund_amount,
    )


def evaluate(ctx: RefundContext) -> Verdict:
    """Decide a refund from structured facts only. Pure and deterministic."""
    denies = _hard_denies(ctx)
    if denies:
        return _verdict(Decision.DENY, denies, refund_amount=0.0)

    escalations = _escalations(ctx)
    if escalations:
        return _verdict(Decision.ESCALATE, escalations, refund_amount=0.0)

    return _verdict(Decision.APPROVE, ["P-CLEAN-APPROVE"], refund_amount=ctx.refund_amount)
