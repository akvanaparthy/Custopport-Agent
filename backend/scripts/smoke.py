"""Live smoke test: one real Claude turn through the full agent, printing the
verdict + reply + a trace summary. Validates the live AnthropicLLM path
(tool-use loop, classification, engine, respond, output-validation).

Run from the backend/ directory:
    .venv/Scripts/python.exe scripts/smoke.py
"""
from __future__ import annotations

import pathlib
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))  # backend/

import anthropic

from app.agent import AnthropicLLM, IdentityContext, run_agent
from app.config import get_settings
from app.contracts import IdentityMode
from app.db.database import connect, init_db
from app.db.seed import ensure_seeded
from app.observability.db import init_observability


def main() -> None:
    settings = get_settings()
    if not settings.anthropic_api_key:
        sys.exit("ANTHROPIC_API_KEY not set in backend/.env")

    conn = connect(":memory:")
    init_db(conn)
    init_observability(conn)
    ensure_seeded(conn, datetime.now(timezone.utc))

    llm = AnthropicLLM(anthropic.Anthropic(api_key=settings.anthropic_api_key))
    result = run_agent(
        messages=[{"role": "user", "content": "My wireless headphones arrived broken. I'd like a refund, please."}],
        identity=IdentityContext(mode=IdentityMode.AUTHENTICATED, customer_id="cust_01"),
        conn=conn, llm=llm,
        conversation_id="conv_smoke", message_id="msg_smoke",
    )

    print(f"model:   {settings.default_model}")
    print(f"outcome: {result.outcome}")
    if result.verdict:
        print(f"verdict: {result.verdict.decision.value}  refs={result.verdict.policy_refs}")
    print(f"reply:   {result.reply}\n")
    print("trace:")
    rows = conn.execute(
        """SELECT step_index, step_type, name, status, retry_count,
                  input_tokens, output_tokens, cost_usd, latency_ms
           FROM steps WHERE run_id = ? ORDER BY step_index""",
        (result.run_id,),
    ).fetchall()
    total_cost = 0.0
    for r in rows:
        total_cost += r["cost_usd"]
        print(f"  [{r['step_index']}] {r['step_type']}/{r['name']} {r['status']} "
              f"retries={r['retry_count']} tok={r['input_tokens']}/{r['output_tokens']} "
              f"${r['cost_usd']:.5f} {r['latency_ms']}ms")
    print(f"\ntotal cost: ${total_cost:.5f}")
    conn.close()


if __name__ == "__main__":
    main()
