# Windows configuration
set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]

# Default recipe when you just type 'just'
_default:
    @just --list

# Server commands
# Django start development server
rs:
    uv run manage.py runserver

# Labb UI start development server
slu:
    uv run labb dev


# Django management
# Create superuser
csu:
    uv run manage.py createsuperuser

# Collect static
cs:
    uv run manage.py collectstatic --noinput

# django shell
sh:
    uv run manage.py shell

# Django create migration
mm:
    uv run manage.py makemigrations


# Database
# Django db shell
dsh:
    uv run manage.py dbshell

# Django db migrate
m:
    uv run manage.py migrate


# Code quality
# Run ruff linter with fix
rc:
    uv run ruff check --fix .

# Run ruff format with fix
rf:
    uv run ruff format .

# Run ruff linter with fix and unsafe fixes
rcu:
    uv run ruff check --fix --unsafe-fixes .

# Run mypy type checker
mc:
    uv run mypy .

# Run Djlint lint
djl:
    uv run djlint --lint .

# Run Djlint format
djf:
    uv run djlint --reformat .


# Testing
# Run django test
test:
    uv run manage.py test

# Run pytest
pytest:
    uv run pytest


# Dependencies
# Install packages
i:
    uv sync

# Install packages including dev
id:
    uv sync --dev


# Pre-commit
# Run pre-commit hooks
pc:
    uv run pre-commit run

# Run pre-commit hooks for all files
pca:
    uv run pre-commit run --all-files
