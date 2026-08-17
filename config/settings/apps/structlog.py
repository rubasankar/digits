"""
django-structlog configuration.
"""

from typing import Any

import structlog

from .environ import env

# Apps & middleware

# Merged into INSTALLED_APPS / MIDDLEWARE in base.py.

STRUCTLOG_APPS = [
    "django_structlog",
]

STRUCTLOG_MIDDLEWARE = [
    "django_structlog.middlewares.RequestMiddleware",
]


# Shared pre-chain
#
# Runs for:
#   - stdlib/Django logging records
#   - native structlog events
#
# The final renderer is intentionally NOT included here.

_SHARED_PRE_CHAIN: list[Any] = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_logger_name,
    structlog.stdlib.add_log_level,
    structlog.stdlib.ExtraAdder(),
    structlog.processors.TimeStamper(
        fmt="iso",
        utc=True,
    ),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,
    structlog.processors.UnicodeDecoder(),
]


# Native structlog configuration
#
# structlog.get_logger() -> stdlib -> ProcessorFormatter
#
# This keeps native structlog logging consistent with Django/stdlib logging.

structlog.configure(
    processors=[
        *_SHARED_PRE_CHAIN,
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)


# Django LOGGING configuration
#
# The final renderer is selected through DJANGO_LOG_FORMATTER:
#
#   json    -> production
#   console -> local development

STRUCTLOG_LOGGING: dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "structlog.stdlib.ProcessorFormatter",
            "processors": [
                structlog.contextvars.merge_contextvars,
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.JSONRenderer(),
            ],
            "foreign_pre_chain": _SHARED_PRE_CHAIN,
        },
        "console": {
            "()": "structlog.stdlib.ProcessorFormatter",
            "processors": [
                structlog.contextvars.merge_contextvars,
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.dev.ConsoleRenderer(colors=True),
            ],
            "foreign_pre_chain": _SHARED_PRE_CHAIN,
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": env(
                "DJANGO_LOG_FORMATTER",
                default="json",
            ),
        },
    },
    "root": {
        "handlers": ["console"],
        "level": env(
            "DJANGO_LOG_LEVEL",
            default="INFO",
        ),
    },
    "loggers": {
        # Don't flood logs with invalid Host headers.
        "django.security.DisallowedHost": {
            "level": "ERROR",
            "propagate": True,
        },
        # Django request errors/warnings.
        "django.request": {
            "level": "WARNING",
            "propagate": True,
        },
    },
}
