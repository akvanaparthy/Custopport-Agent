"""Cheap, toggleable guard checks. These are defense-in-depth, NOT the wall —
the wall is the deterministic engine + code-gated actions. The input guard only
flags (it never decides); output validation asserts the communicated verdict
matches the engine's and repairs the message if not."""
from __future__ import annotations

import re

_INJECTION_PATTERNS = [
    r"ignore (?:all |the |your )?(?:previous|prior|above)",
    r"disregard (?:all |the |your )?(?:previous|prior|above|instructions|rules)",
    r"forget (?:your|the|all) (?:rules|instructions)",
    r"you are now",
    r"new instructions",
    r"system prompt",
    r"\boverride\b",
    r"pretend (?:to|you)",
    r"act as (?:if|a|an)",
    r"approve (?:it|this|the refund) anyway",
]
_COMPILED = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]


def scan_injection(text: str) -> dict:
    hits = [p.pattern for p in _COMPILED if p.search(text or "")]
    return {"flagged": bool(hits), "patterns": hits}


def verdicts_match(communicated: str | None, engine: str) -> bool:
    return communicated == engine
