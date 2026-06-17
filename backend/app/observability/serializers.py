"""Pydantic response models + row->model builders for the admin API. JSON TEXT
columns (input/output/attempts/error) are decoded back into objects here."""
from __future__ import annotations

import json
import sqlite3
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


def _loads(value: Optional[str]) -> Any:
    return json.loads(value) if value else None


class StepView(BaseModel):
    step_index: int
    step_type: str
    name: str
    status: str
    input: Any = None
    output: Any = None
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cost_usd: float
    latency_ms: int
    retry_count: int
    attempts: Any = None
    error: Any = None
    started_at: str


class RunSummary(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    run_id: str
    conversation_id: str
    identity_mode: str
    customer_id: Optional[str]
    model: str
    final_verdict: Optional[str]
    status: str
    total_cost_usd: float
    total_latency_ms: int
    total_input_tokens: int
    total_output_tokens: int
    step_count: int
    started_at: str
    finished_at: Optional[str]


class RunDetail(RunSummary):
    steps: list[StepView] = []


class OrderView(BaseModel):
    order_id: str
    customer_id: str
    item_name: str
    category: str
    order_total: float
    currency: str
    status: str
    order_date: str
    delivered_date: Optional[str]
    is_final_sale: bool
    item_condition: str
    already_refunded: bool
    refunded_amount: float
    refunded_at: Optional[str]


def to_step_view(row: sqlite3.Row) -> StepView:
    return StepView(
        step_index=row["step_index"], step_type=row["step_type"], name=row["name"],
        status=row["status"], input=_loads(row["input_json"]), output=_loads(row["output_json"]),
        input_tokens=row["input_tokens"], output_tokens=row["output_tokens"],
        cache_read_tokens=row["cache_read_tokens"], cost_usd=row["cost_usd"],
        latency_ms=row["latency_ms"], retry_count=row["retry_count"],
        attempts=_loads(row["attempts_json"]), error=_loads(row["error_json"]),
        started_at=row["started_at"],
    )


def to_run_summary(row: sqlite3.Row, step_count: int) -> RunSummary:
    return RunSummary(
        run_id=row["run_id"], conversation_id=row["conversation_id"],
        identity_mode=row["identity_mode"], customer_id=row["customer_id"], model=row["model"],
        final_verdict=row["final_verdict"], status=row["status"],
        total_cost_usd=row["total_cost_usd"], total_latency_ms=row["total_latency_ms"],
        total_input_tokens=row["total_input_tokens"], total_output_tokens=row["total_output_tokens"],
        step_count=step_count, started_at=row["started_at"], finished_at=row["finished_at"],
    )


def to_run_detail(row: sqlite3.Row, step_rows: list[sqlite3.Row]) -> RunDetail:
    summary = to_run_summary(row, len(step_rows))
    return RunDetail(**summary.model_dump(), steps=[to_step_view(s) for s in step_rows])


def to_order_view(row: sqlite3.Row) -> OrderView:
    return OrderView(
        order_id=row["order_id"], customer_id=row["customer_id"], item_name=row["item_name"],
        category=row["category"], order_total=row["order_total"], currency=row["currency"],
        status=row["status"], order_date=row["order_date"], delivered_date=row["delivered_date"],
        is_final_sale=bool(row["is_final_sale"]), item_condition=row["item_condition"],
        already_refunded=bool(row["already_refunded"]), refunded_amount=row["refunded_amount"],
        refunded_at=row["refunded_at"],
    )
