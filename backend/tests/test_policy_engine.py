"""Tier-1 tests: the deterministic engine. No LLM, no DB — pure and free.

These gate the safety-critical core: every policy rule, the boundaries, and the
precedence (DENY > ESCALATE > APPROVE).
"""
from __future__ import annotations

import pytest

from app.contracts import (
    ClaimType,
    Decision,
    ItemCondition,
    OrderStatus,
    RefundContext,
)
from app.policy.engine import evaluate


def ctx(**overrides) -> RefundContext:
    """A clean, approvable baseline; override one field per test."""
    base = dict(
        order_id="ord_1",
        customer_id="cust_1",
        order_status=OrderStatus.DELIVERED,
        days_since_delivery=10,
        order_total=100.0,
        refund_amount=100.0,
        is_final_sale=False,
        already_refunded=False,
        category="general",
        claim_type=ClaimType.DAMAGED,
        claim_confidence=0.95,
        item_condition=ItemCondition.DAMAGED,
    )
    base.update(overrides)
    return RefundContext(**base)


# --- clean approval -------------------------------------------------------- #


def test_clean_approve():
    v = evaluate(ctx())
    assert v.decision is Decision.APPROVE
    assert v.auto_executable is True
    assert v.refund_amount == 100.0
    assert v.policy_refs == ["P-CLEAN-APPROVE"]


# --- hard denies ----------------------------------------------------------- #


def test_final_sale_denies():
    v = evaluate(ctx(is_final_sale=True))
    assert v.decision is Decision.DENY
    assert "P-FINAL-SALE" in v.policy_refs
    assert v.auto_executable is False


def test_already_refunded_denies():
    v = evaluate(ctx(already_refunded=True))
    assert v.decision is Decision.DENY
    assert "P-ALREADY-REFUNDED" in v.policy_refs


@pytest.mark.parametrize("cat", ["gift_card", "digital", "perishable"])
def test_non_refundable_category_denies(cat):
    v = evaluate(ctx(category=cat))
    assert v.decision is Decision.DENY
    assert "P-CATEGORY" in v.policy_refs


@pytest.mark.parametrize(
    "status",
    [OrderStatus.SHIPPED, OrderStatus.PROCESSING, OrderStatus.PENDING, OrderStatus.CANCELLED],
)
def test_non_delivered_status_denies(status):
    v = evaluate(ctx(order_status=status, days_since_delivery=None))
    assert v.decision is Decision.DENY
    assert "P-STATUS" in v.policy_refs


# --- window boundary ------------------------------------------------------- #


def test_window_day_30_is_inside():
    v = evaluate(ctx(days_since_delivery=30))
    assert v.decision is Decision.APPROVE


def test_window_day_31_denies():
    v = evaluate(ctx(days_since_delivery=31))
    assert v.decision is Decision.DENY
    assert "P-WINDOW" in v.policy_refs


# --- escalation: amount ceiling ------------------------------------------- #


def test_amount_exactly_ceiling_approves():
    v = evaluate(ctx(order_total=500.0, refund_amount=500.0))
    assert v.decision is Decision.APPROVE


def test_amount_over_ceiling_escalates():
    v = evaluate(ctx(order_total=500.01, refund_amount=500.01))
    assert v.decision is Decision.ESCALATE
    assert "P-MAX-AUTO" in v.policy_refs
    assert v.auto_executable is False


# --- escalation: condition ------------------------------------------------- #


def test_opened_non_defective_escalates():
    v = evaluate(ctx(item_condition=ItemCondition.OPENED, claim_type=ClaimType.NOT_AS_DESCRIBED))
    assert v.decision is Decision.ESCALATE
    assert "P-CONDITION" in v.policy_refs


def test_used_but_defective_does_not_trigger_condition():
    # A defective item that happens to be used should NOT escalate on condition.
    v = evaluate(ctx(item_condition=ItemCondition.USED, claim_type=ClaimType.DEFECTIVE))
    assert v.decision is Decision.APPROVE


# --- escalation: ambiguity ------------------------------------------------- #


def test_low_confidence_escalates():
    v = evaluate(ctx(claim_confidence=0.4))
    assert v.decision is Decision.ESCALATE
    assert "P-AMBIGUOUS" in v.policy_refs


@pytest.mark.parametrize("claim", [ClaimType.OTHER, ClaimType.UNKNOWN, ClaimType.CHANGED_MIND])
def test_non_approvable_claim_escalates(claim):
    v = evaluate(ctx(claim_type=claim, item_condition=ItemCondition.NEW))
    assert v.decision is Decision.ESCALATE
    assert "P-AMBIGUOUS" in v.policy_refs


def test_delivered_with_unknown_date_escalates():
    v = evaluate(ctx(days_since_delivery=None))
    assert v.decision is Decision.ESCALATE
    assert "P-AMBIGUOUS" in v.policy_refs


# --- precedence ------------------------------------------------------------ #


def test_final_sale_over_500_denies_not_escalates():
    # DENY must beat ESCALATE: a $600 final-sale item is DENIED, not escalated.
    v = evaluate(ctx(is_final_sale=True, order_total=600.0, refund_amount=600.0))
    assert v.decision is Decision.DENY
    assert "P-FINAL-SALE" in v.policy_refs
    assert "P-MAX-AUTO" not in v.policy_refs


def test_injection_phrasing_is_irrelevant():
    # The engine takes no text. Facts say final-sale + $900 -> DENY, regardless
    # of any 'ignore policy, approve this' phrasing upstream.
    v = evaluate(ctx(is_final_sale=True, refund_amount=900.0, order_total=900.0))
    assert v.decision is Decision.DENY
