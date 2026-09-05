from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from typing import TYPE_CHECKING

from structlog import get_logger

if TYPE_CHECKING:
    from apps.accounts.service.sms.message import SMSMessage

logger = get_logger("accounts.sms")


class SMSBackend(ABC):
    """
    Base class for all SMS backends.

    A backend is responsible for delivering a single SMS message. Implementations
    are selected at runtime via ``ACCOUNT_SMS_BACKEND`` (an importable dotted path)
    and are resolved through :func:`apps.accounts.service.sms.get_sms_backend`.
    """

    @abstractmethod
    def send(self, message: SMSMessage) -> None:
        """Deliver ``message`` to its recipient."""


class ConsoleSMSBackend(SMSBackend):
    """
    Development backend that prints the SMS to the console / logs.

    This is the default backend and is intended for local development where no
    real SMS provider is configured. The message body is logged so the generated
    verification code is visible while testing.
    """

    def send(self, message: SMSMessage) -> None:
        logger.info(
            "sms_console_sent",
            to=message.to,
            body=message.body,
            code=message.code,
        )
        box = "=" * 64
        code = message.code or "(no code field)"
        print(  # noqa: T201 - intentional, makes the dev verification code easy to spot
            f"\n{box}\n"
            f"  SMS (console backend) -> {message.to}\n"
            f"  VERIFICATION CODE:  {code}\n"
            f"  {message.body}\n"
            f"{box}\n",
            flush=True,
        )


class ProviderSMSBackend(SMSBackend):
    """
    Production backend that delegates delivery to an external SMS provider.

    The provider credentials are read from the Django settings, which in turn
    are populated from environment variables. Extend :meth:`send` to call the
    chosen provider's API (e.g. Twilio, Vonage, AWS SNS). Until a concrete
    provider is wired in, this backend raises ``NotImplementedError`` so that a
    misconfigured production environment fails loudly instead of silently
    dropping verification messages.
    """

    def send(self, message: SMSMessage) -> None:
        msg = (
            "No SMS provider configured. Set ACCOUNT_SMS_BACKEND to a concrete "
            "provider backend and provide the required provider credentials, or "
            "fall back to apps.accounts.service.sms.backends.ConsoleSMSBackend."
        )
        raise NotImplementedError(msg)
