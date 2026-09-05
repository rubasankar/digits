---
name: project-conventions
description: Digits' domain architecture rules - service-layer placement, snapshot/ledger patterns, financial integrity, and mypy-strict annotation requirements. Always consult this before writing or reviewing any code under apps/ or core/ in this repo: adding a view, model, form, or manager method, touching inventory/orders/payments logic, or reviewing a diff for architectural fit. Not needed for pure templates, static assets, or config-only changes.
user-invocable: false
---

# Digits domain architecture conventions

This repo (`agent.md` has the full picture) is a Django e-commerce platform organized as 15
domain-bounded apps + a shared `core` package. The rules below aren't style preferences - each
one exists to keep money, stock, and history correct in a multi-app system where mistakes are
expensive to unwind. Apply them by default; don't wait to be reminded.

## Service layer placement

Business logic lives in each app's `service/` package, not in `views.py` or `models.py`.
Views handle HTTP concerns (parsing requests, returning responses) and models handle
persistence/query concerns (fields, managers, querysets) - the actual decision-making
(can this order be cancelled? what's the effective price? is this stock movement valid?)
belongs in `service/`. When you're about to add a conditional or a multi-step operation to a
view or model method, stop and ask whether it's actually domain logic that belongs in the
service layer instead.

Each app owns its own state machine through its service layer - don't reach into another
app's models or querysets to drive a transition (e.g. don't flip an `orders` status field
from `payments` code). Cross-app orchestration goes through the *owning* app's service
functions, so the owning app stays the single place that can enforce its own invariants.

## Ledger and snapshot patterns

- **Inventory is an append-only ledger.** `StockMovement`-style records are never updated or
  deleted after creation - a correction is a new movement, not an edit. If you find yourself
  writing code that mutates a past stock record, the fix is a new record, not an `UPDATE`.
- **Orders/financial records snapshot at creation time.** Historical data (price paid, tax
  rate, address) is preserved via JSON/decimal snapshot fields on the order itself, not via
  live foreign-key lookups to `catalogue`/`pricing`/`customers`. A later price or address
  change must never retroactively alter a past order's numbers.
- **Financial integrity is enforced at the database level.** Accounting formulas (totals,
  balances) should have `CheckConstraint`s backing them, not just application-level
  validation - the DB is the last line of defense against a bug producing an inconsistent
  ledger.
- **Status changes get audit trails.** Major entities (orders, returns, payments) log
  transitions into a dedicated status-history table rather than only overwriting a `status`
  field, so "how did this get here" is always answerable.

## Code-level rules

- Every function and method must be fully type-annotated - mypy strict mode (with
  django-stubs) runs across the whole repo in CI, and untyped code will fail it.
- No `print` or `assert` statements in production code paths (`apps/`, `core/`). `assert` is
  fine in `tests/` - pytest relies on it there, and `ruff.toml` already carves out
  per-file-ignores for test/hook code.

## When reviewing a diff

Flag it (don't silently fix, unless asked) when you see: domain logic added to a view or
model instead of a service; a stock/ledger record being mutated instead of appended; an order
field derived from a live join instead of a stored snapshot; a financial total without a
matching `CheckConstraint`; or an untyped function in `apps/`/`core/`.
