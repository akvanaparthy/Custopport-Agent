"""Run the adversarial matrix LIVE and emit a scorecard (console + json + md).

    cd backend
    RUN_LIVE_EVAL=1 .venv/Scripts/python.exe -m eval.runner

Needs ANTHROPIC_API_KEY in backend/.env. Each case is a full real agent run on
an isolated DB, so this makes ~N live calls and costs a few cents per case.
"""
from __future__ import annotations

import json
import pathlib
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))  # backend/

from eval.harness import (  # noqa: E402
    CaseResult,
    load_cases,
    make_live_llm,
    run_case,
    validate_cases,
)
from app.db.seed import CUSTOMERS  # noqa: E402

OUT_DIR = pathlib.Path(__file__).resolve().parent
CHATS_DIR = pathlib.Path(__file__).resolve().parents[2] / "chats"  # repo root /chats
CUSTOMER_NAMES = {cid: name for cid, name, _ in CUSTOMERS}


def _line(r: CaseResult) -> str:
    mark = "PASS" if r.passed else "FAIL"
    refs = ",".join(r.policy_refs) if r.policy_refs else "-"
    money = "MONEY!" if r.refund_executed else "no-money"
    leak = " LEAK!" if r.leaked else ""
    return (f"  [{mark}] {r.case.id:<16} {r.case.category:<16} "
            f"expect={r.case.expect:<8} outcome={r.outcome:<9} "
            f"decision={r.decision or '-':<9} refs={refs:<16} {money}{leak}")


def main() -> int:
    cases = load_cases()
    problems = validate_cases(cases)
    if problems:
        print("Matrix invalid:")
        for p in problems:
            print(f"  - {p}")
        return 2

    try:
        llm = make_live_llm()
    except RuntimeError as exc:
        print(exc)
        print("Set RUN_LIVE_EVAL=1 and add ANTHROPIC_API_KEY to backend/.env.")
        return 2

    now = datetime.now(timezone.utc)
    print(f"Running {len(cases)} adversarial cases against the live agent...\n")
    results: list[CaseResult] = []
    for c in cases:
        r = run_case(c, llm, now)
        results.append(r)
        print(_line(r))

    adversarial = [r for r in results if r.case.expect == "held"]
    controls = [r for r in results if r.case.expect == "approved"]
    held = [r for r in adversarial if r.passed]
    unauthorized = [r for r in adversarial if r.refund_executed]
    leaks = [r for r in results if r.leaked]
    ctrl_pass = [r for r in controls if r.passed]

    print("\n" + "=" * 72)
    print(f"Adversarial held:        {len(held)}/{len(adversarial)}")
    print(f"Unauthorized refunds:    {len(unauthorized)}")
    print(f"PII / prompt leaks:      {len(leaks)}")
    print(f"Controls approved:       {len(ctrl_pass)}/{len(controls)}")
    all_pass = len(held) == len(adversarial) and len(ctrl_pass) == len(controls)
    print(f"RESULT:                  {'ALL PASS' if all_pass else 'FAILURES PRESENT'}")
    print("=" * 72)

    _write_artifacts(results, now)
    _write_transcripts(results, now)
    return 0 if all_pass else 1


def _write_artifacts(results: list[CaseResult], now: datetime) -> None:
    payload = {
        "generated_at": now.isoformat(),
        "total": len(results),
        "summary": {
            "adversarial_held": sum(1 for r in results if r.case.expect == "held" and r.passed),
            "adversarial_total": sum(1 for r in results if r.case.expect == "held"),
            "unauthorized_refunds": sum(1 for r in results if r.case.expect == "held" and r.refund_executed),
            "leaks": sum(1 for r in results if r.leaked),
            "controls_approved": sum(1 for r in results if r.case.expect == "approved" and r.passed),
            "controls_total": sum(1 for r in results if r.case.expect == "approved"),
        },
        "cases": [
            {
                "id": r.case.id, "category": r.case.category, "expect": r.case.expect,
                "outcome": r.outcome, "decision": r.decision, "policy_refs": r.policy_refs,
                "refund_executed": r.refund_executed, "leaked": r.leaked,
                "passed": r.passed, "error": r.error, "run_id": r.run_id,
            }
            for r in results
        ],
    }
    (OUT_DIR / "scorecard.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    s = payload["summary"]
    lines = [
        "# Adversarial eval scorecard",
        "",
        f"_Generated {now.isoformat()} — {payload['total']} cases against the live agent._",
        "",
        f"- **Adversarial held:** {s['adversarial_held']}/{s['adversarial_total']}",
        f"- **Unauthorized refunds:** {s['unauthorized_refunds']}",
        f"- **PII / prompt leaks:** {s['leaks']}",
        f"- **Controls approved:** {s['controls_approved']}/{s['controls_total']}",
        "",
        "| case | category | expect | outcome | decision | refs | money | pass |",
        "|------|----------|--------|---------|----------|------|-------|------|",
    ]
    for r in results:
        refs = ", ".join(r.policy_refs) if r.policy_refs else "—"
        money = "⚠️ MOVED" if r.refund_executed else "none"
        lines.append(
            f"| {r.case.id} | {r.case.category} | {r.case.expect} | {r.outcome} | "
            f"{r.decision or '—'} | {refs} | {money} | {'✅' if r.passed else '❌'} |"
        )
    (OUT_DIR / "scorecard.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nWrote {OUT_DIR / 'scorecard.json'} and scorecard.md")


def _bq(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return "> _(empty)_"
    return "\n".join(f"> {ln}" if ln else ">" for ln in text.splitlines())


def _result_label(r: CaseResult) -> str:
    if r.error:
        return f"❌ ERROR ({r.error})"
    if r.leaked:
        return f"❌ LEAKED {r.leaked}"
    if not r.passed:
        return "❌ FAILED"
    return "✅ HELD — the line held" if r.case.expect == "held" else "✅ APPROVED — legitimate refund"


def _transcript_md(r: CaseResult, now: datetime) -> str:
    c = r.case
    name = CUSTOMER_NAMES.get(c.customer_id, "?")
    refs = ", ".join(r.policy_refs) if r.policy_refs else "—"
    lines = [
        f"# {c.id} — {c.category}",
        "",
        f"- **Customer:** `{c.customer_id}` ({name})",
        f"- **Order:** `{c.order_id}` — {c.note or '—'}",
        f"- **Attack style:** {c.category}",
        f"- **Expected:** {c.expect}",
        f"- **Outcome:** {r.outcome}" + (f" · decision {r.decision}" if r.decision else "") + f" · policy {refs}",
        f"- **Refund executed:** {'⚠️ YES' if r.refund_executed else 'no'}",
        f"- **Result:** {_result_label(r)}",
        "",
        "---",
        "",
    ]
    for turn in c.to_messages():
        who = "🧑 Customer" if turn["role"] == "user" else "🤖 Agent"
        lines += [f"**{who}**", "", _bq(turn["content"]), ""]
    lines += ["**🤖 Agent — reply**", "", _bq(r.reply or "(no reply)"), "", "---",
              f"\n_run `{r.run_id or '—'}` · generated {now.isoformat()}_"]
    return "\n".join(lines) + "\n"


def _write_transcripts(results: list[CaseResult], now: datetime) -> None:
    CHATS_DIR.mkdir(parents=True, exist_ok=True)
    index = [
        "# Adversarial eval — chat transcripts",
        "",
        f"_Generated {now.isoformat()} · {len(results)} cases run live against the agent._",
        "",
        "Each row is a real conversation: the customer's (adversarial) message and the",
        "agent's actual reply. `held` means the attack did not move money.",
        "",
        "| transcript | style | order | result |",
        "|------------|-------|-------|--------|",
    ]
    for r in results:
        fname = f"{r.case.id}.md"
        (CHATS_DIR / fname).write_text(_transcript_md(r, now), encoding="utf-8")
        index.append(
            f"| [{r.case.id}]({fname}) | {r.case.category} | `{r.case.order_id}` | "
            f"{'✅' if r.passed else '❌'} {r.outcome} |"
        )
    (CHATS_DIR / "README.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    print(f"Wrote {len(results)} transcripts to {CHATS_DIR}")


if __name__ == "__main__":
    raise SystemExit(main())
