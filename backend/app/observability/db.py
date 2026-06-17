"""Trace + settings tables (live in the same SQLite file as the domain data).

A run = one agent turn. steps[] is the ordered per-node trace the admin
dashboard renders; a retry folds into its step row (retry_count + attempts_json),
never a new row. The settings table is a single override row (id=1); NULL columns
fall through to env defaults. step_type CHECK = the canonical StepType enum."""
from __future__ import annotations

import sqlite3

TRACE_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id                  TEXT PRIMARY KEY,
    conversation_id         TEXT NOT NULL,
    message_id              TEXT NOT NULL,
    identity_mode           TEXT NOT NULL CHECK (identity_mode IN ('authenticated','in_chat')),
    customer_id             TEXT,
    model                   TEXT NOT NULL,
    final_verdict           TEXT CHECK (final_verdict IN ('APPROVE','DENY','ESCALATE') OR final_verdict IS NULL),
    status                  TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running','completed','error')),
    total_input_tokens      INTEGER NOT NULL DEFAULT 0,
    total_output_tokens     INTEGER NOT NULL DEFAULT 0,
    total_cache_read_tokens INTEGER NOT NULL DEFAULT 0,
    total_cost_usd          REAL NOT NULL DEFAULT 0,
    total_latency_ms        INTEGER NOT NULL DEFAULT 0,
    started_at              TEXT NOT NULL,
    finished_at             TEXT
);

CREATE TABLE IF NOT EXISTS steps (
    step_id           TEXT PRIMARY KEY,
    run_id            TEXT NOT NULL REFERENCES runs(run_id),
    step_index        INTEGER NOT NULL,
    step_type         TEXT NOT NULL CHECK (step_type IN
                        ('input_guard','llm','tool','policy_engine','action','output_validation')),
    name              TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'ok' CHECK (status IN ('ok','error')),
    input_json        TEXT,
    output_json       TEXT,
    input_tokens      INTEGER NOT NULL DEFAULT 0,
    output_tokens     INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd          REAL NOT NULL DEFAULT 0,
    latency_ms        INTEGER NOT NULL DEFAULT 0,
    retry_count       INTEGER NOT NULL DEFAULT 0,
    attempts_json     TEXT,
    error_json        TEXT,
    started_at        TEXT NOT NULL,
    UNIQUE (run_id, step_index)
);

CREATE TABLE IF NOT EXISTS settings (
    id                        INTEGER PRIMARY KEY CHECK (id = 1),
    model                     TEXT,
    effort                    TEXT CHECK (effort IN ('low','medium','high','max') OR effort IS NULL),
    adaptive_thinking         INTEGER,
    max_tokens                INTEGER,
    input_guard_enabled       INTEGER,
    output_validation_enabled INTEGER,
    identity_mode             TEXT CHECK (identity_mode IN ('authenticated','in_chat') OR identity_mode IS NULL),
    persona                   TEXT,
    updated_at                TEXT
);

CREATE INDEX IF NOT EXISTS idx_runs_started ON runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_steps_run ON steps(run_id, step_index);
"""


def init_observability(conn: sqlite3.Connection) -> None:
    conn.executescript(TRACE_SCHEMA)
    conn.commit()
