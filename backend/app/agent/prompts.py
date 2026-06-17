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
        "Your job in this phase is to identify which order the request is about and "
        "categorize the claim, then hand off. Use the read-only tools to find the "
        "customer's order(s). You do NOT decide refunds — a deterministic policy "
        "engine does that from the facts; you only gather and classify.\n\n"
        "Be decisive. As soon as you've identified the order and the customer has "
        "given any reason, call `classify_claim(order_id, claim_type, confidence)` "
        "immediately — do not ask follow-up questions you don't strictly need. Map "
        "common phrasings: 'broken / arrived broken / damaged / cracked' -> damaged; "
        "'defective / faulty / won't turn on / stopped working' -> defective; "
        "'wrong item / not what I ordered' -> wrong_item; 'not as described / "
        "different from the listing' -> not_as_described; 'changed my mind / no "
        "longer want / ordered by mistake' -> changed_mind. Set confidence to how "
        "clearly the reason maps; the engine escalates low-confidence or unclear "
        "claims, so you don't need to be perfect. Only ask a clarifying question if "
        "you genuinely cannot tell which order it is, or the customer gave no reason "
        "at all. Never invent an order id; use only ids returned by the tools.\n\n"
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
