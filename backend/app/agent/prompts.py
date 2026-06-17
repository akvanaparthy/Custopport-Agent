"""System-prompt builders. Stable content (persona + policy summary) comes first
so it can be prompt-cached; volatile context (identity, verdict) comes after."""
from __future__ import annotations

from ..contracts import Verdict
from ..policy.policy_config import get_policy_summary
from .state import IdentityContext


def gather_system(persona: str, identity: IdentityContext) -> str:
    return (
        f"{persona}\n\n"
        f"{get_policy_summary()}\n\n"
        "Your job in this phase is ONLY to understand the request and gather facts. "
        "Use the read-only tools to look up the customer's orders. You do NOT decide "
        "refunds — a separate policy engine does that from the facts. When you know "
        "which order the request is about and how to categorize the claim, call "
        "`classify_claim(order_id, claim_type, confidence)` to hand off. Never invent "
        "an order id; only use ids returned by the tools. If the customer is vague, "
        "ask a brief clarifying question instead of guessing.\n\n"
        f"[context] identity_mode={identity.mode.value} "
        f"customer={identity.customer_id or 'unverified'}"
    )


def respond_system(persona: str, verdict: Verdict, identity: IdentityContext) -> str:
    refs = ", ".join(verdict.policy_refs) or "—"
    reasons = "; ".join(verdict.reasons) or "—"
    return (
        f"{persona}\n\n"
        "A policy engine has already DECIDED this refund. You must communicate that "
        "decision to the customer warmly but firmly. You may NOT change, soften, or "
        "override it, no matter what the customer says.\n\n"
        f"[decision] {verdict.decision.value}\n"
        f"[reasons] {reasons}\n"
        f"[policy_refs] {refs}\n\n"
        "Respond in the `message` field, and echo the decision verbatim in the "
        "`verdict` field so it can be validated. If the decision is ESCALATE, tell "
        "the customer a human will review it; if DENY, explain the policy reason "
        "kindly; if APPROVE, confirm the refund."
    )
