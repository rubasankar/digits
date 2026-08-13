"""
Celery + Redis broker / result-backend configuration.
"""

import ssl

from .environ import env

REDIS_URL = env("REDIS_URL", default="redis://redis:6379/0")
REDIS_SSL = REDIS_URL.startswith("rediss://")

# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------
# TIME_ZONE and USE_TZ are set in base.py; Celery picks them up from there.
# We declare CELERY_TIMEZONE here using the same default so it is always set.
CELERY_TIMEZONE = env("TIME_ZONE", default="UTC")

CELERY_BROKER_URL = REDIS_URL
CELERY_BROKER_USE_SSL = {"ssl_cert_reqs": ssl.CERT_NONE} if REDIS_SSL else None

CELERY_RESULT_BACKEND = REDIS_URL
CELERY_REDIS_BACKEND_USE_SSL = CELERY_BROKER_USE_SSL
CELERY_RESULT_EXTENDED = True
CELERY_RESULT_BACKEND_ALWAYS_RETRY = True
CELERY_RESULT_BACKEND_MAX_RETRIES = 10

CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"

CELERY_TASK_TIME_LIMIT = 5 * 60  # hard limit: 5 min
CELERY_TASK_SOFT_TIME_LIMIT = 60  # soft limit: 1 min

CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_WORKER_SEND_TASK_EVENTS = True
CELERY_TASK_SEND_SENT_EVENT = True
CELERY_WORKER_HIJACK_ROOT_LOGGER = False
