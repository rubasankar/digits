from __future__ import annotations

import pytest

from apps.accounts.service.sms import get_sms_backend
from apps.accounts.service.sms import send_sms
from apps.accounts.service.sms.backends import ConsoleSMSBackend
from apps.accounts.service.sms.backends import ProviderSMSBackend
from apps.accounts.service.sms.backends import SMSBackend
from apps.accounts.service.sms.message import SMSMessage


class TestGetSmsBackend:
    def test_default_backend_when_setting_unset(self):
        backend = get_sms_backend()
        assert isinstance(backend, ConsoleSMSBackend)

    def test_default_backend_when_setting_empty(self, settings):
        settings.ACCOUNT_SMS_BACKEND = ""
        backend = get_sms_backend()
        assert isinstance(backend, ConsoleSMSBackend)

    def test_configured_backend_path_is_resolved(self, settings):
        settings.ACCOUNT_SMS_BACKEND = (
            "apps.accounts.service.sms.backends.ConsoleSMSBackend"
        )
        backend = get_sms_backend()
        assert isinstance(backend, ConsoleSMSBackend)


class TestSendSms:
    def test_routes_message_to_resolved_backend(self, monkeypatch):
        message = SMSMessage(to="+15125551212", body="Hello", code="1234")
        backend = RecordingBackend()
        monkeypatch.setattr(
            "apps.accounts.service.sms.get_sms_backend",
            lambda: backend,
        )
        send_sms(message)
        assert backend.sent == [message]


class TestBackends:
    def test_console_backend_prints_verification_code(self, capsys):
        message = SMSMessage(to="+15125551212", body="Your code", code="9999")
        ConsoleSMSBackend().send(message)
        output = capsys.readouterr().out
        assert "VERIFICATION CODE:  9999" in output
        assert "+15125551212" in output
        assert "Your code" in output

    def test_console_backend_handles_missing_code(self, capsys):
        message = SMSMessage(to="+15125551212", body="Hello")
        ConsoleSMSBackend().send(message)
        output = capsys.readouterr().out
        assert "(no code field)" in output

    def test_provider_backend_raises_not_implemented(self):
        message = SMSMessage(to="+15125551212", body="Hello", code="1234")
        with pytest.raises(NotImplementedError, match="No SMS provider configured"):
            ProviderSMSBackend().send(message)


class RecordingBackend(SMSBackend):
    def __init__(self) -> None:
        self.sent: list[SMSMessage] = []

    def send(self, message: SMSMessage) -> None:
        self.sent.append(message)
