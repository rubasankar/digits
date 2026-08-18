from .apps.environ import env
from .base import *  # noqa: F403
from .base import TEMPLATES

# GENERAL
SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="test-secret-key",
)
TEST_RUNNER = "django.test.runner.DiscoverRunner"

# PASSWORDS
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# EMAIL
MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.locmem.EmailBackend",
    },
}

# DEBUGGING FOR TEMPLATES
TEMPLATES[0]["OPTIONS"]["debug"] = True  # type: ignore[index]

# MEDIA
MEDIA_URL = "http://media.testserver/"
