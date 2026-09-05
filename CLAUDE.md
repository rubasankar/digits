# Digits

Self-hosted SMB e-commerce platform. Django 6.1 / Python 3.14, `uv`-managed, service-layer
architecture across 15 domain apps (`apps/`) + a shared `core` package.

**Read `agent.md` first.** It documents the full domain architecture (app boundaries, service
layer pattern, ledger/snapshot/state-machine design principles, tech stack). The
`project-conventions` skill already encodes those architectural rules for code written here, so
this file doesn't restate them - it covers what `agent.md` doesn't: exact commands, the hooks
active in this session, and test/DB layout.

## Commands

Everything runs through `uv`; `Justfile` recipes are shorthand for the same commands:

| Task | Command | Just |
|---|---|---|
| Dev server | `uv run manage.py runserver` | `just rs` |
| Labb UI dev server | `uv run labb dev` | `just slu` |
| Migrate | `uv run manage.py migrate` | `just m` |
| Make migrations | `uv run manage.py makemigrations` | `just mm` |
| Django shell | `uv run manage.py shell` | `just sh` |
| Ruff lint (fix) | `uv run ruff check --fix .` | `just rc` |
| Ruff format | `uv run ruff format .` | `just rf` |
| Mypy (strict) | `uv run mypy .` | `just mc` |
| Djlint check / format | `uv run djlint --lint .` / `--reformat .` | `just djl` / `just djf` |
| pytest | `uv run pytest` | `just pytest` |
| Pre-commit (all files) | `uv run pre-commit run --all-files` | `just pca` |

## Automated hooks (`.claude/hooks/`)

These fire automatically on every `Write`/`Edit` in this session - don't re-run them manually
after each edit; trust the feedback they already gave you and only run the full-repo commands
above for a final sweep across multiple files:

- **`ruff_fix.py`** (PostToolUse) - runs `ruff check --fix` + `ruff format` on the edited `.py`
  file, then reports back any remaining lint errors it couldn't autofix.
- **`mypy_check.py`** (PostToolUse) - runs `mypy` (strict) on the edited `.py` file (skips
  `migrations/`), reporting type errors back to you.
- **`guard_migrations.py`** (PreToolUse) - asks for confirmation before editing a file under
  `*/migrations/*.py` directly. Prefer `uv run manage.py makemigrations` and only hand-edit the
  generated file for data migrations.

## Testing

Tests live in per-app `tests/` packages (`apps/<app>/tests/`), each with its own `conftest.py`
and `factories.py` (factory-boy), plus `test_models.py`, `test_views.py`, etc. Match that layout
for new apps/features rather than a flat `test_*.py` file - see `apps/accounts/tests/` as the
reference example.

## Database

`DATABASES` is driven by `DATABASE_URL` (`ATOMIC_REQUESTS = True`); locally it points at
`sqlite:///db.sqlite3` via `.env`, production uses Postgres via the same setting.

## Python & Django patterns

- **Service module shape**: a single `services.py` for simpler apps (`inventory`, `pricing`,
  `shipping`, `promotions`, `reviews`, `delivery`), a `service/` package once an app has grown
  multiple concerns (`accounts`, `catalogue`, `checkout`, `orders`, `payments`, `shopping`).
  Match whatever the app you're touching already uses - don't split an app's `services.py` into
  a package unless it has actually outgrown one file.
- **Managers/querysets**: query logic lives on a custom `QuerySet` (`querysets.py`); a
  `Manager["Model"]` subclass (`managers.py`) exposes it via `get_queryset()` (see
  `apps/catalogue/managers.py`/`querysets.py`). Add new query methods there, not as ad hoc
  `.filter(...)` chains inline in views/services.
- **Choices**: use `models.TextChoices` in the app's `enums.py` (or `core/enums.py` for
  cross-app enums), not bare string/int constants.
- **Circular imports**: use `from __future__ import annotations` and a `TYPE_CHECKING` block for
  model imports needed only for type hints, rather than a runtime import you don't need at
  runtime (see `apps/catalogue/managers.py`).
- **Validation**: field/form-level validation goes in the app's `validators.py`, not inlined in
  a form or a model's `clean()`, unless it's a genuine single one-off check.

## Docstrings

Most functions here have none - the code is expected to read clearly on its own. Where one
exists, it's a single sentence stating what the function does/returns, e.g. `"""Return an
active category by slug or None."""` - never restate the signature or type hints in prose, and
never write a multi-paragraph docstring. Reach for more than one line only when there's a real
non-obvious constraint or invariant behind the code (see
`AttributeProvision.get_missing_required_labels` in `apps/catalogue/service/attribute.py` for
the rare justified case) - that's the exception, not the default.

## Generating code

Match the shape of what's already there instead of adding new structure. Don't introduce a new
management command, settings flag, config file, or helper "for later" - if a task needs a
function, add it to the existing `services.py`/`service/` module it belongs in; if it needs
validation, add it to the existing `validators.py`. Create a new file/command/abstraction only
when the task actually can't be done without one.

## Text generation: ASCII only

Write plain ASCII punctuation in code, docs, commit messages, and comments - straight quotes
(`'`/`"`) not curly ones, a plain hyphen `-` for dashes (not en/em dashes), `->`/`<-`/`=>` for
arrows, and `*` for bullets. No non-breaking or other special spaces.

`scripts/fix_non_ascii.py` already runs as a pre-commit hook and auto-corrects exactly these
"AI formatting artifact" characters on commit, but generating plain ASCII the first time avoids
the round-trip and keeps diffs clean before they're ever staged.
