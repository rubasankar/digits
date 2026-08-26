# digits

**Self-Hosted SMB E-Commerce Platform**

A full-stack, self-hosted e-commerce platform for small-to-medium businesses covering the complete order lifecycle: catalogue, checkout, payments, fulfilment, returns, and refund reconciliation.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.14 |
| Framework | Django 6.1 |
| Async tasks / Cache / Sessions | Celery + Redis |
| ASGI server | Gunicorn + uvicorn workers |
| Authentication | django-allauth (MFA, social login), Argon2 password hashing |
| Admin | Django admin themed with `django-unfold` |
| UI | django-cotton / labbui + Tailwind CSS + daisyUI (server-rendered) |
| Logging | django-structlog (structured logging) |
| Feature flags | django-waffle |
| Categories | django-treebeard (materialized-path tree) |
| Countries | django-countries |
| Image processing | django-imagekit |
| Package manager | uv |
| Code quality | ruff + mypy strict |
| Testing | pytest + factory-boy |

---

## Architecture Overview

16 packages under domain boundaries: 15 Django apps in `apps/`, plus a shared `core` package. Business logic lives almost exclusively in `service/` sub-packages (or a top-level `services.py` for simpler apps) - never in views or models. Models hold schema, field-level validation, and `clean()` invariants; models generally do **not** call other apps' services directly, and views generally do **not** write to models directly - they call into the owning app's service layer. Cross-app orchestration (e.g. checkout creating an order, a shipped fulfilment updating stock) always goes through the owning service, so each app stays the single source of truth for its own state machine.

| App | Responsibility |
|---|---|
| `core` | Not a domain app - shared abstract models (`BaseModel`, `AddressBaseModel`), the `DomainError` exception hierarchy every service raises from, cross-app enums, auth decorators (`require_customer`, ...), and the `sample_data` management command. |
| `accounts` | The single identity/auth source for every user on the platform - `UserAccount` (email-based), MFA via allauth. Staff and customers are both `UserAccount`s; `apps.staff`/`apps.customers` attach a profile on top. |
| `catalogue` | Products, categories (tree), brands, variants, images, and a category-scoped EAV attribute system (see below). |
| `pricing` | `Currency`, per-variant `Pricing` rows (BASE/SALE, per currency, with validity windows), `TaxClass`/`TaxRate`. |
| `inventory` | Warehouse-scoped `Stock` and an append-only `StockMovement` ledger (receipts, sales, reservations, returns, adjustments, transfers). |
| `shopping` | `Cart`/`CartItem` (guest and customer, with `ACTIVE`/`SAVED`/`BUY_NOW`/`MERGED` types and guest->customer cart merge on login), plus `Wishlist`. |
| `promotions` | `Campaign` -> `Discount` -> `Coupon` hierarchy, redemption tracking with usage limits. |
| `checkout` | The session-based checkout flow (address -> shipping -> payment -> confirmation) that ends in creating an `Order` via `apps.orders`. |
| `orders` | Owns the `Order`/`OrderItem`/`OrderStatusHistory` lifecycle and the full return-request workflow (`ReturnRequest` -> `ReturnRequestItem` -> `ReturnShipment`). |
| `payments` | A **ledger, not a payment engine** - `Payment`/`Refund`/`PaymentStatusHistory` record what a gateway (e.g. Stripe) reports; this app doesn't decide gateway-side outcomes. |
| `delivery` | Owns fulfilment for every order item via `Fulfilment`, regardless of type. Routes physical/carrier-bound items (`shipment`, `local_delivery`) to `apps.shipping`; handles non-carrier types (`store_pickup`, digital delivery) entirely itself. |
| `shipping` | Carrier accounts, `ShippingMethod`s, and `Shipment`/label/tracking records - only for the carrier-bound fulfilment types `delivery` hands off to it. |
| `customers` | `CustomerProfile` and `CustomerAddress` (shipping/billing/both, one default per role). |
| `staff` | `StaffProfile` and `StaffDepartment`. Fine-grained permissions are Django `Group`s/permissions, not a custom ACL; the staff-facing "dashboard" is the Django admin site. |
| `reviews` | Product reviews with verified-purchase detection and staff moderation. |
| `notifications` | Scaffolded app, not yet implemented (no models beyond the Django default). Reserved for email/in-app notification dispatch. |

---

## How an order actually flows through the system

This is the path a single purchase takes across app boundaries - useful for orienting yourself before changing any one app in isolation.

1. **Catalogue** - a `Product` always has at least one `ProductVariant`; every price, stock row, cart line, and order line is keyed to a *variant*, never the product directly. Category-scoped `AttributeAssignment`s (via `apps.catalogue.service.attribute.AttributeProvision`) determine which attributes a product/variant needs, including which are `is_required` - a product/variant can't be activated while a required attribute is still blank.
2. **Shopping** - `CartService` resolves the current price (via `pricing`) and checks available stock (via `inventory`) before letting a line's quantity increase. A guest cart merges into the customer's cart on login (`CartMergeService`), respecting the same stock cap as a normal add.
3. **Checkout** - `CheckoutService` drives the session through `ADDRESS -> SHIPPING -> PAYMENT -> CONFIRMATION`, snapshotting the chosen shipping/billing address and shipping method, then calls `OrderService.place_order()`.
4. **Orders** - `OrderService.place_order()` snapshots addresses/pricing as plain JSON/decimal fields on the `Order` (so later catalogue or address edits never rewrite history), reserves stock per line, and creates one `Fulfilment` per line via `delivery`. `Order.status` (`PENDING -> CONFIRMED -> PROCESSING -> SHIPPED -> DELIVERED`, plus `CANCELLED`/return states) advances automatically where there's a clear trigger (payment confirmed, all lines shipped/delivered) and via staff admin actions otherwise.
5. **Payments** - `PaymentService`/`RefundService` record gateway-reported state transitions (`PENDING -> PROCESSING -> PAID -> ...`) and keep `Order.payment_status` in sync; a `Payment` reaching `PAID` is what advances the order to `CONFIRMED`.
6. **Delivery** - `FulfilmentService` runs each `Fulfilment` through its own state machine (`PENDING -> ALLOCATED -> PICKED -> PACKED -> SHIPPED -> DELIVERED`). Carrier-bound types hand off to `shipping` post-commit (never inside the same DB transaction as the status write, so a carrier/network failure can't roll back an already-committed transition); `store_pickup` never touches `shipping` at all. When every fulfillable line on an order has shipped/delivered, the order advances too.
7. **Returns** - `ReturnRequestService` runs `PENDING -> APPROVED -> RETURN_SHIPPED -> RECEIVED -> COMPLETED` (or `REJECTED`/`CANCELLED`), restocking via `inventory` on `RECEIVED` and moving `Order.status` to `RETURN_REQUESTED`/`RETURNED` at the right points. A completed return permanently counts against that item's returnability - it can't be returned twice.

---

## Key Design Decisions

**Immutable stock ledger**
Every inventory change is a `StockMovement` record with before/after quantity snapshots. Movement types cover sales, reservations, receipts, returns, adjustments, and transfers. `Stock.quantity` is only ever mutated through `StockMovementService`, never written to directly.

**Order and item snapshots**
Product pricing, attributes, and delivery addresses are snapshotted as JSON/plain fields at the moment an order is placed. Historical order data survives any future catalogue or address changes.

**DB-level financial integrity**
`CheckConstraint` definitions enforce accounting formulas (e.g. `total = subtotal - discount + shipping + tax`) and prevent negative stock quantities or over-refunding at the database level, backing up the service-layer checks rather than replacing them.

**Full return lifecycle**
Return requests follow a defined state machine: `PENDING -> APPROVED -> RETURN_SHIPPED -> RECEIVED -> COMPLETED`. Reaching `COMPLETED` triggers automatic restock and is permanent - it can't be re-returned.

**Category-scoped EAV attributes**
`catalogue` uses a lightweight EAV system rather than per-product columns: `AttributeDefinition` (schema) -> `AttributeAssignment` (per category + scope) -> `ProductAttributeValue`/`VariantAttributeValue` (the actual data, stored as strings with typed coercion on read). An `other_attributes` JSON field on `Product`/`ProductVariant` is the escape hatch for ad-hoc data that doesn't warrant a formal attribute definition.

**Single default currency today, multi-currency-ready model**
`Pricing` already stores rows per `(variant, currency)`, but nothing currently resolves a customer's locale to a non-default currency - the whole storefront reads through the one `Currency` flagged `is_default`. The `pricing` app carries a documented `TODO` for a future `CurrencyRate` model to support live conversion without touching the per-variant `Pricing` rows.

**Payments is a ledger, not an engine**
`apps.payments` only records what a payment gateway reports (via `PaymentService.handle_webhook()` or an explicit `transition_status()` call) - it never computes or decides a gateway-side outcome. The one local computation it does perform (rolling up confirmed `Refund` rows into the `Payment`'s aggregate REFUNDED/PARTIALLY_REFUNDED status) is documented as a fallback that a future gateway-reported payment-level status should take priority over.

**Audit trail**
Dedicated status history tables (`OrderStatusHistory`, `FulfilmentStatusHistory`, `PaymentStatusHistory`, `ReturnRequestStatusHistory`, ...) record every state transition with a timestamp and actor.

---

## Project Structure

```
apps/<app_name>/
    models/          # or models.py if simple
    service/         # business logic only (or services.py for simpler apps)
    migrations/
    admin.py
    apps.py
    constants.py
    enums.py
    managers.py
    querysets.py
    validators.py
    views.py
    forms.py
```

Shared and reusable utilities live in `core/` (abstract base models, the `DomainError` hierarchy, cross-app enums, auth decorators). Settings are split under `config/settings/` (`base.py`, `development.py`, `production.py`, `test.py`) and read from environment variables via `django-environ`.

---

## Getting Started

**Prerequisites**

- Python 3.14
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Redis
- PostgreSQL (`DATABASE_URL` - see `config/settings/base.py`)

**Install dependencies**

```powershell
uv sync
```

**Configure environment**

```powershell
copy .env.example .env
# Edit .env and fill in required values
```

**Apply migrations**

```powershell
uv run python manage.py migrate
```

**Load sample data (optional)**

```powershell
uv run python manage.py sample_data --help
```

**Start the development server**

```powershell
uv run python manage.py runserver
```

**Start with ASGI (production-like)**

```powershell
uv run uvicorn config.asgi:application --reload
```

**Start the Celery worker**

```powershell
uv run celery -A config.celery_app worker
```

---

## Development Commands

```powershell
uv run ruff check --fix --unsafe-fixes   # lint
uv run ruff format                        # format
uv run mypy .                             # type check
uv run pytest                             # run tests
uv run djlint --check templates/          # template lint
```

---

## Code Quality Standards

- **mypy strict** mode with `django-stubs` - every function and method must be fully annotated
- **ruff** enforces no `print` statements (T20), single-line imports (isort), and no star imports
- **Pre-commit hooks** run secrets detection (`detect-secrets`, `gitleaks`), ruff, and djlint on every commit
- No `assert` statements in production code paths
