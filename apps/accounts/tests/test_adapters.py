from __future__ import annotations

from unittest import mock
from unittest.mock import patch

import pytest
from django.http import HttpResponseRedirect

from apps.accounts.adapters import AccountAdapter
from apps.accounts.adapters import SocialAccountAdapter


@pytest.fixture
def adapter():
    return AccountAdapter()


@pytest.fixture
def social_adapter():
    return SocialAccountAdapter()


@pytest.mark.django_db
class TestAccountAdapter:
    def test_is_open_for_signup(self, adapter, rf):
        request = rf.get("/")
        assert adapter.is_open_for_signup(request) is True

    @patch(
        "allauth.account.internal.flows.phone_verification"
        ".ChangePhoneVerificationProcess",
    )
    def test_post_login_redirects_unverified_phone(
        self, mock_process, adapter, user, rf
    ):
        user.phone = "+919876543210"
        user.phone_verified = False
        user.save(update_fields=["phone", "phone_verified"])

        request = rf.post("/")
        request.user = user

        response = adapter.post_login(
            request,
            user,
            email_verification="none",
            signal_kwargs=None,
            email=None,
            signup=False,
            redirect_url=None,
        )
        assert isinstance(response, HttpResponseRedirect)
        assert response.url == "/auth/phone/verify/"
        mock_process.initiate.assert_called_once_with(request, "+919876543210")

    def test_post_login_no_phone_redirects_to_change(self, adapter, user, rf):
        user.phone = ""
        user.phone_verified = False
        user.save(update_fields=["phone", "phone_verified"])

        request = rf.post("/")
        request.user = user

        response = adapter.post_login(
            request,
            user,
            email_verification="none",
            signal_kwargs=None,
            email=None,
            signup=False,
            redirect_url=None,
        )
        assert isinstance(response, HttpResponseRedirect)
        assert response.url == "/auth/phone/change/"

    @patch(
        "allauth.account.adapter.DefaultAccountAdapter.post_login",
        return_value=HttpResponseRedirect("/"),
    )
    def test_post_login_verified_phone_passes_through(
        self, mock_super, adapter, user, rf
    ):
        user.phone = "+919876543210"
        user.phone_verified = True
        user.save(update_fields=["phone", "phone_verified"])

        request = rf.post("/")
        request.user = user

        response = adapter.post_login(
            request,
            user,
            email_verification="none",
            signal_kwargs=None,
            email=None,
            signup=False,
            redirect_url=None,
        )
        assert isinstance(response, HttpResponseRedirect)
        mock_super.assert_called_once()

    @patch(
        "allauth.account.adapter.DefaultAccountAdapter.post_login",
        return_value=HttpResponseRedirect("/"),
    )
    def test_post_login_disabled_verification_passes_through(
        self, mock_super, adapter, user, rf, settings
    ):
        user.phone = "+919876543210"
        user.phone_verified = False
        user.save(update_fields=["phone", "phone_verified"])

        request = rf.post("/")
        request.user = user

        original = settings.ACCOUNT_PHONE_VERIFICATION_ENABLED
        settings.ACCOUNT_PHONE_VERIFICATION_ENABLED = False
        try:
            response = adapter.post_login(
                request,
                user,
                email_verification="none",
                signal_kwargs=None,
                email=None,
                signup=False,
                redirect_url=None,
            )
            assert isinstance(response, HttpResponseRedirect)
            mock_super.assert_called_once()
        finally:
            settings.ACCOUNT_PHONE_VERIFICATION_ENABLED = original

    def test_get_phone_returns_none_for_non_user_account(self, adapter):
        assert adapter.get_phone("not-a-user") is None

    def test_get_phone_returns_none_without_phone(self, adapter, user):
        user.phone = ""
        user.save(update_fields=["phone"])
        assert adapter.get_phone(user) is None

    def test_get_phone_returns_phone_and_verification_flag(self, adapter, user, rf):
        user.phone = "+919876543210"
        user.phone_verified = True
        user.save(update_fields=["phone", "phone_verified"])

        assert adapter.get_phone(user) == ("+919876543210", True)

    def test_set_phone_noops_for_non_user_account(self, adapter):
        target = mock.MagicMock()
        adapter.set_phone(target, "+919876543210", verified=True)
        target.save.assert_not_called()

    def test_set_phone_stores_phone_with_verification_flag(self, adapter, user):
        adapter.set_phone(user, "+919876543210", verified=True)
        user.refresh_from_db()
        assert user.phone == "+919876543210"
        assert user.phone_verified is True

    def test_set_phone_marks_phone_unverified(self, adapter, user):
        adapter.set_phone(user, "+919876543210", verified=False)
        user.refresh_from_db()
        assert user.phone == "+919876543210"
        assert user.phone_verified is False

    def test_set_phone_verified_noops_for_non_user_account(self, adapter):
        target = mock.MagicMock()
        adapter.set_phone_verified(target, "+919876543210")
        target.save.assert_not_called()

    def test_set_phone_verified_marks_phone_verified(self, adapter, user):
        adapter.set_phone_verified(user, "+919876543210")
        user.refresh_from_db()
        assert user.phone == "+919876543210"
        assert user.phone_verified is True


@pytest.mark.django_db
class TestSocialAccountAdapter:
    def test_is_open_for_signup(self, social_adapter, rf):
        request = rf.get("/")
        social_login = None
        assert social_adapter.is_open_for_signup(request, social_login) is True
