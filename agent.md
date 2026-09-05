# digits Agent Documentation

## Overview

This is a self-hosted e-commerce platform for small-to-medium businesses (SMB) built with Django 6.1 and Python 3.14. The platform implements a domain-driven architecture with 15 Django apps plus a shared `core` package.

## Architecture

### Core Structure
- **15 Django Apps**: `accounts`, `catalogue`, `checkout`, `customers`, `delivery`, `inventory`, `notifications`, `orders`, `payments`, `pricing`, `promotions`, `reviews`, `shipping`, `shopping`, `staff`
- **Shared Core Package**: Contains abstract models, exception hierarchy, cross-app enums, auth decorators
- **Service Layer Architecture**: Business logic lives in service packages (`service/` subdirectories), not in views or models

### Domain Boundaries
Each app represents a bounded context with its own domain logic:
- `core`: Shared abstract models and utilities
- `accounts`: Authentication and user identity management
- `catalogue`: Product, category, brand, variant, attribute management
- `pricing`: Currency, pricing, tax management
- `inventory`: Stock tracking and movement ledger
- `shopping`: Cart and wishlist functionality
- `promotions`: Campaigns, discounts, coupons
- `checkout`: Session-based checkout flow
- `orders`: Order lifecycle and return management
- `payments`: Payment ledger system
- `delivery`: Fulfillment management
- `shipping`: Carrier accounts and shipping methods
- `customers`: Customer profiles and addresses
- `staff`: Staff profiles and permissions
- `reviews`: Product review system

## Key Design Principles

1. **Immutable stock ledger**: Append-only `StockMovement` records for every inventory change
2. **Order snapshots**: Historical data preserved through JSON/decimal field snapshots
3. **Database-level financial integrity**: CheckConstraints enforce accounting formulas
4. **Full return lifecycle**: Complete state machine for return requests
5. **Category-scoped EAV attributes**: Flexible product data system
6. **Audit trails**: Dedicated status history tables for all major entities

## Technology Stack

- **Language**: Python 3.14
- **Framework**: Django 6.1
- **Async Tasks**: Celery + Redis
- **ASGI Server**: Gunicorn + uvicorn workers
- **Authentication**: django-allauth (MFA, social login), Argon2 password hashing
- **Admin Interface**: django-unfold theming
- **Frontend**: django-cotton / labbui + Tailwind CSS + daisyUI (server-rendered)
- **Package Manager**: uv
- **Code Quality**: ruff + mypy strict
- **Testing**: pytest + factory-boy

## Development Workflow

### Setup
1. Install Python 3.14, Redis, PostgreSQL
2. Run `uv sync` to install dependencies
3. Copy `.env.example` to `.env` and configure environment variables
4. Run `python manage.py migrate` to apply migrations
5. Start development server with `python manage.py runserver`

### Key Commands
```bash
uv run ruff check --fix --unsafe-fixes   # lint
uv run ruff format                        # format
uv run mypy .                             # type check
uv run pytest                             # run tests
uv run djlint --check templates/          # template lint
```

## Project Structure

```
apps/<app_name>/
    models/          # or models.py if simple
    service/         # business logic only
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

core/                # Shared utilities and abstract models
config/settings/     # Django settings configuration
```

## Contribution Guidelines

1. Business logic should reside in service layers, not views or models
2. Each app maintains its own state machine through services
3. Cross-app orchestration goes through owning app's service layer
4. All functions and methods must be fully annotated with mypy strict mode
5. No print statements or assert statements in production code paths
6. Pre-commit hooks run secrets detection, ruff, and djlint on every commit

## Key Patterns

- **Service Layer Pattern**: Business logic isolated in service packages
- **Domain Error Hierarchy**: Custom exceptions for domain-specific errors
- **Snapshot Architecture**: Historical data preservation through JSON fields
- **State Machine Management**: Dedicated status history tables for all major entities
