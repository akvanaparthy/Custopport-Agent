"""Code mirror of data/policy.md. The engine reads ONLY from here, and
`get_policy_summary()` renders from the same constants, so the summary the LLM
sees can never drift from the rules the engine enforces. A drift test binds this
module to policy.md.

This module is pure: no clock, no DB, no network, no file I/O at decision time.
"""
from __future__ import annotations

from ..contracts import NON_REFUNDABLE_CATEGORIES

# Anchored thresholds (mirror policy.md).
RETURN_WINDOW_DAYS = 30
AUTO_APPROVE_CEILING = 500.0
CLASSIFY_CONFIDENCE_THRESHOLD = 0.6

# Conditions that force human review on an otherwise-eligible return.
ESCALATE_CONDITIONS = frozenset({"used", "opened"})

# Policy reference codes -> one-line human descriptions (used in verdicts and
# the rendered summary).
POLICY_REFS: dict[str, str] = {
    "P-WINDOW": f"Refunds are only auto-approved within {RETURN_WINDOW_DAYS} days of delivery.",
    "P-FINAL-SALE": "Final-sale items are non-refundable.",
    "P-ALREADY-REFUNDED": "An order that has already been refunded cannot be refunded again.",
    "P-STATUS": "Only delivered orders are eligible for a refund.",
    "P-CATEGORY": "Gift cards, digital goods, and perishables are non-refundable.",
    "P-MAX-AUTO": f"Refunds over ${AUTO_APPROVE_CEILING:,.2f} must be escalated to a human.",
    "P-CONDITION": "Items reported used/opened (without a defect) are escalated for review.",
    "P-AMBIGUOUS": "Claims that cannot be confidently classified are escalated.",
    "P-CLEAN-APPROVE": "Within-window delivered orders with a clear refundable reason are approved.",
}


def get_policy_summary() -> str:
    """Render the policy summary the LLM is given. Built from the same
    constants the engine reads — single source, no drift."""
    lines = [
        "Refund policy summary:",
        f"- Return window: {RETURN_WINDOW_DAYS} days from delivery (day {RETURN_WINDOW_DAYS} is inside, day {RETURN_WINDOW_DAYS + 1} is outside).",
        f"- Auto-approval ceiling: ${AUTO_APPROVE_CEILING:,.2f} (above this, a human must approve).",
        f"- Non-refundable categories: {', '.join(sorted(NON_REFUNDABLE_CATEGORIES))}.",
        "- Final-sale items are never refundable.",
        "- Only delivered orders are eligible; already-refunded orders cannot be refunded again.",
        "- Damaged/defective/not-as-described/wrong-item are refundable reasons.",
        "- Used/opened (non-defective) returns and unclear claims are escalated to a human.",
    ]
    return "\n".join(lines)
