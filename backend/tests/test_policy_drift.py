"""Drift test: policy.md (human source of truth) and policy_config.py (code
mirror) must reference exactly the same set of policy rules. If someone edits one
without the other, this fails."""
from __future__ import annotations

import pathlib
import re

from app.policy.policy_config import POLICY_REFS

POLICY_MD = pathlib.Path(__file__).resolve().parents[2] / "data" / "policy.md"
_REF_RE = re.compile(r"P-[A-Z]+(?:-[A-Z]+)*")


def test_policy_md_and_config_refs_match():
    md_text = POLICY_MD.read_text(encoding="utf-8")
    md_refs = set(_REF_RE.findall(md_text))
    code_refs = set(POLICY_REFS)

    missing_from_md = code_refs - md_refs
    extra_in_md = md_refs - code_refs

    assert not missing_from_md, f"refs in code but not policy.md: {sorted(missing_from_md)}"
    assert not extra_in_md, f"refs in policy.md but not code: {sorted(extra_in_md)}"


def test_every_ref_has_a_description():
    assert all(POLICY_REFS.values()), "every policy ref needs a human description"
