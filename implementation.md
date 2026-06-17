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
- [x] `backend/app/policy/engine.py` — pure `evaluate(ctx) -> Verdict`; precedence hard-DENY > ESCALATE > APPROVE
- [x] `backend/app/db/{schema.sql, database.py, repository.py, seed.py}` — 15 customers; idempotent version-gated seed; `now` injected; ownership-scoped reads; guarded `process_refund`; admin reset
- [x] `backend/tests/test_policy_engine.py` — every rule + boundaries (day 30/31, $500/$500.01, precedence, injection-irrelevance) — 25 tests green
- [x] `backend/tests/test_policy_drift.py` — `set(POLICY_REFS) == policy.md refs` (9/9 aligned)
- [x] `backend/tests/test_seed.py` — idempotent; every terminal verdict seeded; ownership scoping; refund guard; full reset — 22 tests (47 total green)

## 3. Observability + settings store + operator data
*Verify: scripted run writes 6 ordered steps; totals == sum of steps; `PUT /api/admin/settings` then `GET` reflects override; `temperature` → 422; orders reset clears refund linkage.*
- [x] `observability/{db.py, trace_recorder.py, pricing.py, serializers.py, admin_router.py}` — trace store + admin API; runs list/detail + SSE stream
- [x] `settings/{store.py, schema.py}` + `config.py` — env defaults overlaid by SQLite; `get_effective_config()` per request; sampling params 422
- [x] order endpoints: list / edit status / full reset / reset-seed (admin-only, agent-inaccessible) — tested via TestClient
- [x] `app/main.py` factory (lifespan init+seed) + `deps.py` (request-scoped conn) + `/api/health` — **75 tests green, no key**

## 4. Orchestration
*Verify: forced-fault run shows a retried step with both attempts; injection transcript never yields unauthorized APPROVE (mocked LLM).*
- [x] `agent/{state,prompts,llm,tools,guards,graph,runner}.py` — LangGraph graph; reuses trace_recorder/settings/repository/policy.engine (no dupes); `agent/` has zero FastAPI imports (clean separation)
- [x] manual observable LLM loop; read-only tools to LLM; `process_refund` code-only & verdict-gated (money only on engine APPROVE)
- [x] stop_reason hardening — refusal/max_tokens/context-exceeded/pause → fail-closed ESCALATE
- [x] deterministic demo fault (cursed order) → visible retry trace step, tested
- [x] orchestration tests (mocked LLM, no key): clean approve, final-sale deny, >$500 escalate, injection-held, cross-customer blocked, output-validation repair, cursed retry, full trace — **93 tests green**

## 5. Identity + guardrails
*Verify: authenticated cross-customer access fails; in_chat verify-then-fetch; output-validation mismatch fails closed; guards OFF still blocks injection.*
- [x] `identity/session.py` — server-side sessions (authenticated bind + in_chat deterministic verify); IDOR scoping in `db/repository` + `agent/tools`
- [x] `agent/guards.py` — InputGuard (injection scan) + OutputValidator (verdict-match), toggleable; covered by tests

## 6. FastAPI app wiring
*Verify: `/api/health` ok; `/api/session` → session_id; `/api/chat` SSE emits coarse status events; all `/api/admin/*` respond.*
- [x] `app/main.py` (lifespan init+seed) + `chat_router` (`/api/session`, `/api/session/verify`, `/api/chat` SSE, `/api/customers`) + `admin_router`; thin layer over `run_agent` — verified live

## 7. Frontend
*Verify: chat round-trips; `/admin` Runs&Traces drill-down shows tool I/O + tokens + cost + latency + retries; Settings PUT works; Data tab resets an order.*
- [x] Vite+React+TS+Tailwind (builds clean), typed `api.ts`/`types.ts` + SSE reader, `/admin` console: Runs & Traces (per-step drill-in — tool I/O, tokens, cost, latency, retries/errors), Settings (live config, no temperature), Data (order edit/reset + reset-seed), chat→trace deep-link
- [x] **UI/UX redesign** (light · lime · glass, iOS/macOS vibrancy, Framer Motion): animated chat hero + recommended prompts; customer **Orders** page (bento cards + eligibility hint + "request refund" → chat), **order detail** modal, **account panel**; **support tickets/history** (persisted per exchange, `/history`); polished console. Backend: session-scoped `/api/orders`, `/api/tickets` (+ tests, 109 green)

## 8. Eval Tier-2 (adversarial)
*Verify: `RUN_LIVE_EVAL=1 python -m eval.runner` — injection/pleading/spoofing/cross-customer never move money; scorecard emitted.*
- [x] `backend/eval/`: `harness.py` (whole-DB money-delta invariant — closes the error-path money hole + ignores the seed's prior refund), `cases/matrix.yaml` (22 curated) + `cases/redteam.yaml` (30 generated by a red-team workflow across 10 attack styles), `runner.py` (scorecard + per-case chat transcripts → `chats/`)
- [x] **Live run vs real Claude: 50/50 attacks held, 0 unauthorized refunds, 0 leaks, 2/2 controls approved** — `eval/scorecard.md`. `tests/test_eval_matrix.py`: matrix-validity + 3 invariant-soundness pins; **115 tests green, no key**. Golden Loom scenarios tagged (clean approve, cursed retry, final-sale deny, >$500 escalate, cross-customer block, injection held)

## 9. Deploy / packaging
*Verify: `docker compose up` and `make dev` both boot, seed, and serve same-origin; missing key → friendly fail-fast.*
- [x] `backend/Dockerfile` + `frontend/Dockerfile` (multi-stage) + `nginx.conf` + root `docker-compose.yml` (single-origin) — **`docker compose up` verified: backend healthy, SPA served, /api proxied**. `.env.example` (root + backend), `Makefile`, `setup.ps1`/`dev.ps1`, `.gitattributes`, README with local + Docker + DigitalOcean deploy. Uvicorn boot also verified out of the box.

## 10. Polish + Loom dry-run
*Verify: walk 6 golden scenarios incl. the failed/retried step; cost/latency callouts accurate.*
- [ ] final pass
