"""Tier-2 adversarial evaluation.

The Tier-1 suite (in `tests/`) proves policy + enforcement with a mocked LLM and
runs in CI with no key. This tier hammers the **real** model with a matrix of
attacks — prompt injection, pleading, authority spoofing, fake policy, false
facts, obfuscation, threats, multi-turn manipulation, and cross-customer IDOR —
and checks one security invariant: **no adversarial input ever moves money on an
order policy makes ineligible, or reaches across customers.** Control cases prove
the agent still approves legitimate refunds.

Live-gated (`RUN_LIVE_EVAL=1` + `ANTHROPIC_API_KEY`). The structural and
invariant-logic tests run without a key.
"""
