# Implementation Checklist

Living, verification-gated checklist. An item is checked **only when its
verification passes** (test green / endpoint actually works) — never just because
a file was written. Full plan: `Plan.md`. Branch: `feat/refund-agent`.

## 1. Contracts + bootstrap
*Verify: clean `pip install -r backend/requirements.txt` succeeds; `python -c "import app.contracts, app.policy.policy_config"` imports; the 9 policy refs match across policy.md ↔ policy_config.*
- [x] `data/policy.md` — 9 anchored policy refs (P-WINDOW … P-CLEAN-APPROVE)
- [x] `backend/app/contracts.py` — enums, `RefundContext`/`Verdict`, `AgentSettings`, pricing, `StepType`/`SSEEvent`
- [x] `backend/app/policy/policy_config.py` — thresholds mirror policy.md; `get_policy_summary()`
- [x] `backend/requirements.txt` — pins resolve+install in a clean venv (verified)
- [x] `implementation.md` created

## 2. Data + engine + Tier-1 tests
*Verify: `pytest` (no API key) green for engine + drift + seed.*
- [ ] `backend/app/policy/engine.py` — pure `evaluate(ctx) -> Verdict`; precedence hard-DENY > ESCALATE > APPROVE
- [ ] `backend/app/db/{schema.sql, repository.py, seed.py}` — 15 customers; idempotent version-gated seed; `now` injected (engine reads no clock)
- [ ] `backend/tests/test_policy_engine.py` — every rule + boundaries (day 30/31, $500/$500.01, mixed final-sale, already-refunded, low-confidence→escalate)
- [ ] `backend/tests/test_policy_drift.py` — `set(POLICY_REFS) == policy.md "Policy Ref" anchors`
- [ ] `backend/tests/test_seed.py` — idempotent; at least one order per terminal verdict

## 3. Observability + settings store + operator data
*Verify: scripted run writes 6 ordered steps; totals == sum of steps; `PUT /api/admin/settings` then `GET` reflects override; `temperature` → 422; orders reset clears refund linkage.*
- [ ] `observability/{db.py, trace_recorder.py, pricing.py, serializers.py, admin_router.py}`
- [ ] `settings/{store.py, schema.py}` — env defaults overlaid by SQLite; `get_effective_config()` per request
- [ ] order endpoints: list / edit status / full reset / reset-seed (admin-only, agent-inaccessible)

## 4. Orchestration
*Verify: forced-fault run shows a retried step with both attempts; injection transcript never yields unauthorized APPROVE (mocked LLM).*
- [ ] `agent/{graph.py, state.py, nodes/*, llm_client.py, tools.py, refund_service.py, trace.py, prompts.py, runner.py, config_provider.py}`
- [ ] manual observable loop; read-only tools to LLM; `process_refund`/`escalate` code-only & verdict-gated
- [ ] stop_reason hardening (max_tokens / context-exceeded / refusal → fail-closed ESCALATE)
- [ ] deterministic demo fault (seeded "cursed" order) wired into live ToolRegistry

## 5. Identity + guardrails
*Verify: authenticated cross-customer access fails; in_chat verify-then-fetch; output-validation mismatch fails closed; guards OFF still blocks injection.*
- [ ] `identity/{session.py, context.py, dispatcher.py, ownership.py, verify.py}`
- [ ] InputGuard + OutputValidator (toggleable)

## 6. FastAPI app wiring
*Verify: `/api/health` ok; `/api/session` → session_id; `/api/chat` SSE emits coarse status events; all `/api/admin/*` respond.*
- [ ] `app/main.py` + routers; thin layer over `run_agent`

## 7. Frontend
*Verify: chat round-trips; `/admin` Runs&Traces drill-down shows tool I/O + tokens + cost + latency + retries; Settings PUT works; Data tab resets an order.*
- [ ] Vite+React+TS+Tailwind; Chat `/`; `/admin` console (Runs&Traces / Settings / Data); one typed apiClient

## 8. Eval Tier-2 (adversarial)
*Verify: `RUN_LIVE_EVAL=1 pytest` — injection/pleading/spoofing/cross-customer never APPROVE; scorecard emitted.*
- [ ] `backend/eval/` + `cases/matrix.yaml` + `faults.py` + scorecard; 6 golden Loom scenarios

## 9. Deploy / packaging
*Verify: `docker compose up` and `make dev` both boot, seed, and serve same-origin; missing key → friendly fail-fast.*
- [ ] `deploy/` (Dockerfiles, compose, nginx) + `.env.example` + Makefile + README quickstart

## 10. Polish + Loom dry-run
*Verify: walk 6 golden scenarios incl. the failed/retried step; cost/latency callouts accurate.*
- [ ] final pass
