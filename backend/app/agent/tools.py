"""Tools the LLM may call during gathering — all READ-ONLY and identity-scoped.
The money-moving actions (process_refund / escalate) are NOT here; they're run by
code in the `act` node, gated on the engine verdict. Tool scoping is enforced in
code (server-injected customer_id), not via the prompt.

`classify_claim` is the terminal hand-off: when the LLM calls it, gathering ends
and the engine takes over.

The `CURSED_ORDER_ID` carries a demo-only transient fault: the first read raises
`TransientToolError` once, then succeeds — giving the Loom a deterministic
failed/retried trace step. The fault never changes a verdict."""
from __future__ import annotations

from typing import Any

from ..contracts import ClaimType, ItemCondition
from ..db import repository as repo
from ..db.seed import CURSED_ORDER_ID
from ..policy.policy_config import get_policy_summary
from .state import IdentityContext


class TransientToolError(Exception):
    """A transient, retryable tool failure (also reused by the eval fault injector)."""


_CLAIM_VALUES = [c.value for c in ClaimType]

READONLY_TOOL_SCHEMAS: list[dict] = [
    {
        "name": "get_my_orders",
        "description": "List the current customer's orders (id, item, status, total).",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_order",
        "description": "Get details for one of the current customer's orders by id.",
        "input_schema": {
            "type": "object",
            "properties": {"order_id": {"type": "string"}},
            "required": ["order_id"],
        },
    },
    {
        "name": "get_policy_summary",
        "description": "Return the refund policy summary.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "classify_claim",
        "description": (
            "Hand off to the policy engine once you know the order and claim. "
            "Call exactly once when ready."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "claim_type": {"type": "string", "enum": _CLAIM_VALUES},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            },
            "required": ["order_id", "claim_type", "confidence"],
        },
    },
]

# Names the gather loop treats as the terminal hand-off.
TERMINAL_TOOL = "classify_claim"


class ToolRegistry:
    def __init__(self, conn, identity: IdentityContext, *, fault_enabled: bool = True):
        self._conn = conn
        self._identity = identity
        self._fault_enabled = fault_enabled
        self._fired_faults: set[str] = set()

    def schemas(self) -> list[dict]:
        return READONLY_TOOL_SCHEMAS

    def dispatch(self, name: str, args: dict) -> dict:
        if name == "get_my_orders":
            return self._get_my_orders()
        if name == "get_order":
            return self._get_order(args["order_id"])
        if name == "get_policy_summary":
            return {"policy": get_policy_summary()}
        if name == "classify_claim":
            return {"ok": True}  # terminal signal; caller captures the args
        return {"error": f"unknown tool: {name}"}

    # --- read-only impls (scoped to the active customer) ------------------ #

    def _maybe_fault(self, order_id: str) -> None:
        if self._fault_enabled and order_id == CURSED_ORDER_ID and order_id not in self._fired_faults:
            self._fired_faults.add(order_id)
            raise TransientToolError(f"transient glitch reading {order_id}")

    def _get_my_orders(self) -> dict:
        rows = repo.list_orders(self._conn, self._identity.customer_id)
        return {
            "orders": [
                {
                    "order_id": r["order_id"],
                    "item_name": r["item_name"],
                    "status": r["status"],
                    "order_total": r["order_total"],
                }
                for r in rows
            ]
        }

    def _get_order(self, order_id: str) -> dict:
        self._maybe_fault(order_id)
        row = repo.get_order(self._conn, order_id, self._identity.customer_id)
        if row is None:
            return {"error": "order_not_found_for_customer"}
        return {
            "order_id": row["order_id"],
            "item_name": row["item_name"],
            "category": row["category"],
            "order_total": row["order_total"],
            "status": row["status"],
            "delivered_date": row["delivered_date"],
            "is_final_sale": bool(row["is_final_sale"]),
            "item_condition": row["item_condition"],
            "already_refunded": bool(row["already_refunded"]),
        }
