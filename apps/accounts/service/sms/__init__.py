from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings
from django.utils.module_loading import import_string

from apps.accounts.service.sms.backends import ConsoleSMSBackend
from apps.accounts.service.sms.backends import SMSBackend

if TYPE_CHECKING:
    from apps.accounts.service.sms.message import SMSMessage


def get_sms_backend() -> SMSBackend:
    """
    Return the configured SMS backend instance.

    The backend is chosen via ``ACCOUNT_SMS_BACKEND`` (an importable dotted
    path). If unset, the console backend is used, which is appropriate for local
    development. Backends are instantiated once and cached.
    """
    backend_path = getattr(settings, "ACCOUNT_SMS_BACKEND", "")
    if not backend_path:
        return ConsoleSMSBackend()
    return import_string(backend_path)()  # type: ignore[no-any-return]


def send_sms(message: SMSMessage) -> None:
    """Deliver ``message`` using the configured SMS backend."""
    get_sms_backend().send(message)
