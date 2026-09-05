from __future__ import annotations

from apps.accounts.context_processors import allauth_settings


class TestAllauthSettingsProcessor:
    def test_returns_dict(self, rf):
        request = rf.get("/")
        result = allauth_settings(request)
        assert "ACCOUNT_ALLOW_REGISTRATION" in result

    def test_value_matches_setting(self, rf, settings):
        request = rf.get("/")
        result = allauth_settings(request)
        assert (
            result["ACCOUNT_ALLOW_REGISTRATION"] == settings.ACCOUNT_ALLOW_REGISTRATION
        )
