-- SQLite schema for the refund agent's domain data + refund ledger.
-- Trace/observability tables live in observability/ (separate concern).

CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS customers (
    customer_id TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    email       TEXT NOT NULL UNIQUE,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    order_id         TEXT PRIMARY KEY,
    customer_id      TEXT NOT NULL REFERENCES customers(customer_id),
    item_name        TEXT NOT NULL,
    category         TEXT NOT NULL DEFAULT 'general',
    order_total      REAL NOT NULL DEFAULT 0,
    currency         TEXT NOT NULL DEFAULT 'USD',
    status           TEXT NOT NULL CHECK (status IN ('delivered','shipped','processing','pending','cancelled')),
    order_date       TEXT NOT NULL,
    delivered_date   TEXT,
    is_final_sale    INTEGER NOT NULL DEFAULT 0,
    item_condition   TEXT NOT NULL DEFAULT 'new'
                     CHECK (item_condition IN ('new','damaged','defective','used','opened')),
    already_refunded INTEGER NOT NULL DEFAULT 0,
    refunded_amount  REAL NOT NULL DEFAULT 0,
    refunded_at      TEXT
);

-- Ledger: one row per agent verdict (executed=1 only when money actually moved).
CREATE TABLE IF NOT EXISTS refunds (
    refund_id   TEXT PRIMARY KEY,
    order_id    TEXT NOT NULL REFERENCES orders(order_id),
    customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    amount      REAL NOT NULL,
    decision    TEXT NOT NULL CHECK (decision IN ('APPROVE','DENY','ESCALATE')),
    policy_refs TEXT NOT NULL,
    reasons     TEXT NOT NULL,
    executed    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);

-- Server-side sessions: bind a request to one customer. In authenticated mode the
-- customer_id is set at creation; in in_chat mode it's null until verified.
CREATE TABLE IF NOT EXISTS sessions (
    session_id    TEXT PRIMARY KEY,
    identity_mode TEXT NOT NULL CHECK (identity_mode IN ('authenticated','in_chat')),
    customer_id   TEXT,
    verified      INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL,
    last_seen     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_refunds_order ON refunds(order_id);
