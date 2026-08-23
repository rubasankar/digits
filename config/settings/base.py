"""
Base Django configuration.
"""
# ruff: noqa: E402, F403

from pathlib import Path
from typing import Any

import django_stubs_ext

from .apps.allauth import ALLAUTH_APPS
from .apps.allauth import ALLAUTH_MIDDLEWARE
from .apps.compressor import COMPRESSOR_APPS
from .apps.compressor import COMPRESSOR_STATICFILES_FINDERS
from .apps.cotton import COTTON_APPS
from .apps.cotton import COTTON_TEMPLATE_BUILTINS
from .apps.cotton import COTTON_TEMPLATE_LOADERS
from .apps.environ import env
from .apps.imagekit import IMAGEKIT_APPS
from .apps.structlog import STRUCTLOG_APPS
from .apps.structlog import STRUCTLOG_LOGGING
from .apps.structlog import STRUCTLOG_MIDDLEWARE
from .apps.unfold import UNFOLD_APPS

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent

django_stubs_ext.monkeypatch()

# General
DEBUG = env.bool("DJANGO_DEBUG", False)
TIME_ZONE = "UTC"
LANGUAGE_CODE = "en-us"
USE_I18N = True
USE_TZ = True

# Database
DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["ATOMIC_REQUESTS"] = True

# URLs / WSGI
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

DJANGO_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "config.admin.DigitsAdminConfig",
    "django.forms",
]

LOCAL_APPS = [
    "core",
    "apps.accounts",
    "apps.catalogue",
    "apps.checkout",
    "apps.customers",
    "apps.delivery",
    "apps.inventory",
    "apps.notifications",
    "apps.orders",
    "apps.payments",
    "apps.pricing",
    "apps.promotions",
    "apps.reviews",
    "apps.shipping",
    "apps.shopping",
    "apps.staff",
]

THIRD_PARTY_APPS: list[str] = [
    "treebeard",
    "django_countries",
    "labb",
    "labbicons",
]

INSTALLED_APPS = (
    UNFOLD_APPS
    + DJANGO_APPS
    + ALLAUTH_APPS
    + COMPRESSOR_APPS
    + COTTON_APPS
    + IMAGEKIT_APPS
    + STRUCTLOG_APPS
    + LOCAL_APPS
    + THIRD_PARTY_APPS
)


# Authentication
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
AUTH_USER_MODEL = "accounts.UserAccount"
LOGIN_REDIRECT_URL = "core:home"
LOGIN_URL = "account_login"

# Password hashing & validation
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation."
        "UserAttributeSimilarityValidator",
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Middleware
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    *ALLAUTH_MIDDLEWARE,
    *STRUCTLOG_MIDDLEWARE,
]

# Static & media files
STATIC_ROOT = str(BASE_DIR / "staticfiles")
STATIC_URL = "/static/"
STATICFILES_DIRS = [str(BASE_DIR / "static")]
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
    *COMPRESSOR_STATICFILES_FINDERS,
]

MEDIA_ROOT = str(BASE_DIR / "media")
MEDIA_URL = "/media/"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [str(BASE_DIR / "templates")],
        "APP_DIRS": False,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                "django.contrib.messages.context_processors.messages",
            ],
            "loaders": [
                (
                    "django.template.loaders.cached.Loader",
                    [
                        *COTTON_TEMPLATE_LOADERS,
                        "django.template.loaders.filesystem.Loader",
                        "django.template.loaders.app_directories.Loader",
                    ],
                )
            ],
            "builtins": [
                *COTTON_TEMPLATE_BUILTINS,
                "labb.templatetags.lb_tags",
            ],
        },
    },
]

# Fixtures
FIXTURE_DIRS = (str(BASE_DIR / "fixtures"),)

# Email
MAILERS: dict[str, dict[str, Any]] = {
    "default": {
        "BACKEND": "django.core.mail.backends.console.EmailBackend",
    },
}

DEFAULT_FROM_EMAIL = env(
    "DJANGO_DEFAULT_FROM_EMAIL",
    default="digits <noreply@digits.com>",
)

SERVER_EMAIL = env(
    "DJANGO_SERVER_EMAIL",
    default=DEFAULT_FROM_EMAIL,
)

EMAIL_SUBJECT_PREFIX = env(
    "DJANGO_EMAIL_SUBJECT_PREFIX",
    default="[digits] ",
)

ACCOUNT_EMAIL_SUBJECT_PREFIX = EMAIL_SUBJECT_PREFIX


# Admin
ADMIN_URL = "admin/"
ADMINS = ['"Rubasankar" <rubasankar@outlook.in>']
MANAGERS = ADMINS

# Logging -- delegate entirely to the structlog settings module so there is
# a single source of truth for formatters, handlers, and log levels.
LOGGING = STRUCTLOG_LOGGING

# Shipping
# Carrier event codes that indicate a successful delivery.
SHIPPING_DELIVERED_EVENT_CODES: frozenset[str] = frozenset({"DELIVERED", "DEL", "POD"})
# carrier_code used to identify the local-delivery CarrierAccount.
LOCAL_DELIVERY_CARRIER_CODE: str = "local"

from .apps.allauth import *
from .apps.celery import *
from .apps.compressor import *
from .apps.imagekit import *
from .apps.unfold import *
