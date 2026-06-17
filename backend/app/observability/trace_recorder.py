"""TraceRecorder: passive instrumentation the agent loop wraps around each step.

It only times, captures I/O, counts tokens/retries, computes cost, and persists —
it never reads chat text or influences control flow (the verdict stays in the
deterministic engine). A retry folds into its step row (retry_count +
attempts_json); an exception inside a step is recorded (status='error') and
re-raised so the caller still sees it."""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Callable, Iterator, Optional

from . import pricing


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class StepHandle:
    """Mutable accumulator the agent fills in during a step."""

    def __init__(self) -> None:
        self.input: Any = None
        self.output: Any = None
        self.input_tokens = 0
        self.output_tokens = 0
        self.cache_read_tokens = 0
        self.attempts: list[dict] = []
        self.error: Optional[dict] = None

    def set_input(self, obj: Any) -> None:
        self.input = obj

    def set_output(self, obj: Any) -> None:
        self.output = obj

    def set_usage(self, input_tokens: int = 0, output_tokens: int = 0, cache_read_tokens: int = 0) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cache_read_tokens = cache_read_tokens

    def record_retry(self, error: dict) -> None:
        """Log a failed attempt that will be retried (stays on the same step row)."""
        self.attempts.append({"attempt": len(self.attempts) + 1, "status": "error", "error": error})


class TraceRecorder:
    def __init__(self, conn: sqlite3.Connection, now: Optional[Callable[[], str]] = None) -> None:
        self._conn = conn
        self._now = now or _now_iso
        self._models: dict[str, str] = {}

    def start_run(
        self,
        *,
        conversation_id: str,
        message_id: str,
        identity_mode: str,
        customer_id: Optional[str],
        model: str,
    ) -> str:
        run_id = "run_" + uuid.uuid4().hex[:12]
        self._models[run_id] = model
        self._conn.execute(
            """INSERT INTO runs(run_id, conversation_id, message_id, identity_mode,
                   customer_id, model, status, started_at)
               VALUES (?,?,?,?,?,?, 'running', ?)""",
            (run_id, conversation_id, message_id, identity_mode, customer_id, model, self._now()),
        )
        self._conn.commit()
        return run_id

    def _next_index(self, run_id: str) -> int:
        row = self._conn.execute(
            "SELECT COALESCE(MAX(step_index), -1) + 1 AS n FROM steps WHERE run_id = ?", (run_id,)
        ).fetchone()
        return int(row["n"])

    @contextmanager
    def step(self, run_id: str, step_type: str, name: str) -> Iterator[StepHandle]:
        handle = StepHandle()
        index = self._next_index(run_id)
        start = perf_counter()
        try:
            yield handle
        except Exception as exc:  # record, then re-raise — never swallow
            handle.error = {"type": type(exc).__name__, "message": str(exc)[:500]}
            self._write_step(run_id, index, step_type, name, handle, start, status="error")
            raise
        self._write_step(
            run_id, index, step_type, name, handle, start,
            status="error" if handle.error else "ok",
        )

    def _write_step(self, run_id, index, step_type, name, handle: StepHandle, start: float, *, status: str) -> None:
        latency_ms = int((perf_counter() - start) * 1000)
        cost = pricing.cost_usd(
            self._models.get(run_id, ""),
            handle.input_tokens,
            handle.output_tokens,
            handle.cache_read_tokens,
        )
        self._conn.execute(
            """INSERT INTO steps(step_id, run_id, step_index, step_type, name, status,
                   input_json, output_json, input_tokens, output_tokens, cache_read_tokens,
                   cost_usd, latency_ms, retry_count, attempts_json, error_json, started_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "step_" + uuid.uuid4().hex[:12], run_id, index, step_type, name, status,
                _dump(handle.input), _dump(handle.output),
                handle.input_tokens, handle.output_tokens, handle.cache_read_tokens,
                cost, latency_ms, len(handle.attempts),
                _dump(handle.attempts) if handle.attempts else None,
                _dump(handle.error) if handle.error else None,
                self._now(),
            ),
        )
        self._conn.commit()

    def finish_run(self, run_id: str, *, final_verdict: Optional[str], status: str = "completed") -> None:
        totals = self._conn.execute(
            """SELECT COALESCE(SUM(input_tokens),0) i, COALESCE(SUM(output_tokens),0) o,
                      COALESCE(SUM(cache_read_tokens),0) c, COALESCE(SUM(cost_usd),0) cost,
                      COALESCE(SUM(latency_ms),0) lat
               FROM steps WHERE run_id = ?""",
            (run_id,),
        ).fetchone()
        self._conn.execute(
            """UPDATE runs SET final_verdict = ?, status = ?, finished_at = ?,
                   total_input_tokens = ?, total_output_tokens = ?, total_cache_read_tokens = ?,
                   total_cost_usd = ?, total_latency_ms = ?
               WHERE run_id = ?""",
            (final_verdict, status, self._now(), totals["i"], totals["o"], totals["c"],
             totals["cost"], totals["lat"], run_id),
        )
        self._conn.commit()


def _dump(obj: Any) -> Optional[str]:
    if obj is None:
        return None
    return json.dumps(obj, default=str)
