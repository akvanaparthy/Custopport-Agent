# Refund Policy (source of truth)

This document is the human-readable source of truth for refund decisions. The
deterministic engine in `backend/app/policy/policy_config.py` mirrors these
rules verbatim; a drift test (`backend/tests/test_policy_drift.py`) fails if the
two diverge. **Do not change one without the other.**

Decision precedence (highest first): **hard-DENY > ESCALATE > APPROVE**. The
engine evaluates rules in that order and returns the first decisive verdict.

## Rules

### P-WINDOW — Return window
Refunds are only auto-approved within **30 days** of the delivery date. A request
made after the window is **DENIED** (`P-WINDOW`). Day 30 is inside the window;
day 31 is outside.

### P-FINAL-SALE — Final-sale items
Items marked **final sale** are non-refundable. Any such item **DENIES** the
request (`P-FINAL-SALE`). This is a hard deny and overrides the window.

### P-ALREADY-REFUNDED — Already refunded
An order that has already been refunded cannot be refunded again. **DENY**
(`P-ALREADY-REFUNDED`).

### P-STATUS — Order status
Only orders with status **delivered** are eligible. Orders that are
`cancelled`, `pending`, `processing`, or `shipped` are **DENIED** (`P-STATUS`):
either there is nothing to return yet, or the order was never completed.

### P-CATEGORY — Non-refundable categories
Items in non-refundable categories — **gift_card**, **digital**, **perishable** —
are **DENIED** (`P-CATEGORY`).

### P-MAX-AUTO — Auto-approval ceiling
Refunds for more than **$500.00** exceed the agent's auto-approval authority and
must be **ESCALATED** to a human (`P-MAX-AUTO`).

### P-CONDITION — Item condition
If the item is reported **damaged** or **defective**, the claim is eligible for
approval within the window (this is the normal happy path). If the reported
condition is **used** or **opened** on a non-defective return, the case is
**ESCALATED** for human review (`P-CONDITION`).

### P-AMBIGUOUS — Unclassifiable claim
If the claim type cannot be confidently classified from the conversation (low
confidence), the case is **ESCALATED** (`P-AMBIGUOUS`) rather than guessed.

### P-CLEAN-APPROVE — Clean approval
A request that is within the window, on a delivered order, not final-sale, not
already refunded, in a refundable category, at or under the $500 ceiling, with a
clear refundable reason (damaged/defective/not-as-described/wrong-item), is
**APPROVED** (`P-CLEAN-APPROVE`).
