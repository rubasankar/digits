from __future__ import annotations

from apps.accounts.service.sms import get_sms_backend
from apps.accounts.service.sms import send_sms

__all__ = ["get_sms_backend", "send_sms"]
