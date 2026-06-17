"""Idempotent demo seed: 15 customers + orders engineered so the spread exercises
every policy rule and both boundaries.

Window-sensitive orders are anchored to the injected `now` (delivered_date =
now - N days), so day-29/day-31 fixtures stay correct across reseeds and the
engine still reads no clock. Re-seeding is version-gated; `force=True` wipes and
re-seeds (used by the admin "reset to seed" action).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

from ..contracts import ClaimType, Decision

SEED_VERSION = "v1"

# The demo "cursed" order: the live ToolRegistry injects one transient tool
# failure on the first read of this order so the Loom has a deterministic
# failed/retried trace step. The engine verdict is unaffected (clean APPROVE).
CURSED_ORDER_ID = "ord_cursed"

# (customer_id, name, email)
CUSTOMERS = [
    ("cust_01", "Sarah Chen", "sarah.chen@example.com"),
    ("cust_02", "Marcus Webb", "marcus.webb@example.com"),
    ("cust_03", "Aisha Khan", "aisha.khan@example.com"),
    ("cust_04", "Diego Romero", "diego.romero@example.com"),
    ("cust_05", "Lena Fischer", "lena.fischer@example.com"),
    ("cust_06", "Tom Becker", "tom.becker@example.com"),
    ("cust_07", "Priya Nair", "priya.nair@example.com"),
    ("cust_08", "Olu Adeyemi", "olu.adeyemi@example.com"),
    ("cust_09", "Hana Suzuki", "hana.suzuki@example.com"),
    ("cust_10", "Liam O'Brien", "liam.obrien@example.com"),
    ("cust_11", "Grace Park", "grace.park@example.com"),
    ("cust_12", "Noah Schmidt", "noah.schmidt@example.com"),
    ("cust_13", "Maya Patel", "maya.patel@example.com"),
    ("cust_14", "Ivan Petrov", "ivan.petrov@example.com"),
    ("cust_15", "Zoe Martins", "zoe.martins@example.com"),
]

# Each order: scenario-engineered. days = days since delivery (None = not yet
# delivered). claim/confidence are what a customer would assert at runtime;
# expected_decision/ref let test_seed verify the seeded order -> engine path.
ORDERS = [
    # order_id, customer, item, category, total, status, days, final, condition,
    #   refunded, claim_type, confidence, expected_decision, expected_ref
    ("ord_clean", "cust_01", "Wireless Headphones", "electronics", 120.0, "delivered", 10, 0, "damaged", 0, ClaimType.DAMAGED, 0.95, Decision.APPROVE, "P-CLEAN-APPROVE"),
    ("ord_final", "cust_02", "Clearance Jacket", "apparel", 80.0, "delivered", 5, 1, "damaged", 0, ClaimType.DAMAGED, 0.95, Decision.DENY, "P-FINAL-SALE"),
    ("ord_refunded", "cust_03", "Desk Lamp", "home", 60.0, "delivered", 8, 0, "damaged", 1, ClaimType.DAMAGED, 0.95, Decision.DENY, "P-ALREADY-REFUNDED"),
    ("ord_giftcard", "cust_04", "$50 Gift Card", "gift_card", 50.0, "delivered", 3, 0, "new", 0, ClaimType.WRONG_ITEM, 0.9, Decision.DENY, "P-CATEGORY"),
    ("ord_shipped", "cust_05", "Bluetooth Speaker", "electronics", 200.0, "shipped", None, 0, "new", 0, ClaimType.NOT_AS_DESCRIBED, 0.9, Decision.DENY, "P-STATUS"),
    ("ord_expired", "cust_06", "Throw Blanket", "home", 90.0, "delivered", 40, 0, "damaged", 0, ClaimType.DAMAGED, 0.95, Decision.DENY, "P-WINDOW"),
    ("ord_big", "cust_07", "OLED Monitor", "electronics", 750.0, "delivered", 7, 0, "defective", 0, ClaimType.DEFECTIVE, 0.95, Decision.ESCALATE, "P-MAX-AUTO"),
    ("ord_opened", "cust_08", "Skincare Set", "beauty", 40.0, "delivered", 6, 0, "opened", 0, ClaimType.NOT_AS_DESCRIBED, 0.9, Decision.ESCALATE, "P-CONDITION"),
    ("ord_changedmind", "cust_09", "Running Shoes", "apparel", 70.0, "delivered", 4, 0, "new", 0, ClaimType.CHANGED_MIND, 0.9, Decision.ESCALATE, "P-AMBIGUOUS"),
    (CURSED_ORDER_ID, "cust_10", "Mechanical Keyboard", "electronics", 110.0, "delivered", 9, 0, "damaged", 0, ClaimType.DAMAGED, 0.95, Decision.APPROVE, "P-CLEAN-APPROVE"),
    # plain delivered orders for the remaining customers (switcher variety)
    ("ord_n11", "cust_11", "Coffee Grinder", "home", 95.0, "delivered", 12, 0, "damaged", 0, ClaimType.DAMAGED, 0.95, Decision.APPROVE, "P-CLEAN-APPROVE"),
    ("ord_n12", "cust_12", "Yoga Mat", "general", 35.0, "delivered", 15, 0, "defective", 0, ClaimType.DEFECTIVE, 0.95, Decision.APPROVE, "P-CLEAN-APPROVE"),
    ("ord_n13", "cust_13", "Backpack", "general", 60.0, "delivered", 2, 0, "damaged", 0, ClaimType.WRONG_ITEM, 0.9, Decision.APPROVE, "P-CLEAN-APPROVE"),
    ("ord_n14", "cust_14", "Phone Case", "electronics", 25.0, "delivered", 20, 0, "damaged", 0, ClaimType.DAMAGED, 0.95, Decision.APPROVE, "P-CLEAN-APPROVE"),
    ("ord_n15", "cust_15", "Water Bottle", "general", 18.0, "delivered", 1, 0, "defective", 0, ClaimType.DEFECTIVE, 0.95, Decision.APPROVE, "P-CLEAN-APPROVE"),
]


def _scenario_rows():
    """Yield (order_id, claim_type, claim_confidence, expected_decision,
    expected_ref) for the test suite to verify seeded order -> engine verdict."""
    for o in ORDERS:
        yield (o[0], o[10], o[11], o[12], o[13])


def ensure_seeded(conn: sqlite3.Connection, now: datetime, force: bool = False) -> bool:
    """Seed the DB if not already at SEED_VERSION. Returns True if it (re)seeded.
    Idempotent: a second call at the same version is a no-op."""
    row = conn.execute("SELECT value FROM schema_meta WHERE key='seed_version'").fetchone()
    if row is not None and row["value"] == SEED_VERSION and not force:
        return False

    conn.execute("DELETE FROM refunds")
    conn.execute("DELETE FROM orders")
    conn.execute("DELETE FROM customers")

    created_at = now.isoformat()
    conn.executemany(
        "INSERT INTO customers(customer_id, name, email, created_at) VALUES (?,?,?,?)",
        [(cid, name, email, created_at) for (cid, name, email) in CUSTOMERS],
    )

    for (oid, cid, item, cat, total, status, days, final, cond, refunded, *_rest) in ORDERS:
        delivered = (now - timedelta(days=days)).date().isoformat() if days is not None else None
        order_date = (now - timedelta(days=(days + 3) if days is not None else 2)).date().isoformat()
        conn.execute(
            """INSERT INTO orders(order_id, customer_id, item_name, category, order_total,
                   currency, status, order_date, delivered_date, is_final_sale, item_condition,
                   already_refunded, refunded_amount, refunded_at)
               VALUES (?,?,?,?,?,'USD',?,?,?,?,?,?,?,?)""",
            (
                oid, cid, item, cat, total, status, order_date, delivered, final, cond,
                refunded, (total if refunded else 0.0), (created_at if refunded else None),
            ),
        )

    conn.execute(
        "INSERT OR REPLACE INTO schema_meta(key, value) VALUES ('seed_version', ?)",
        (SEED_VERSION,),
    )
    conn.commit()
    return True
