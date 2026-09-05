from __future__ import annotations

from allauth.account.internal.flows.phone_verification import (
    PHONE_VERIFICATION_SESSION_KEY,
)
from django.urls import reverse

from apps.accounts.tests.factories import UserAccountFactory


class TestChangePhoneView:
    def test_post_starts_verification(self, client, db):
        user = UserAccountFactory()
        client.force_login(user)
        url = reverse("account_change_phone")
        response = client.post(url, {"phone": "+919876543210"})
        assert response.status_code == 302
        assert response.url == reverse("account_verify_phone")

    def test_get_renders(self, client, db):
        user = UserAccountFactory()
        client.force_login(user)
        url = reverse("account_change_phone")
        response = client.get(url)
        assert response.status_code == 200

    def test_verify_page_renders(self, client, db):
        user = UserAccountFactory()
        client.force_login(user)
        client.post(reverse("account_change_phone"), {"phone": "+919876543210"})
        response = client.get(reverse("account_verify_phone"))
        assert response.status_code == 200

    def test_full_add_phone_flow_persists(self, client, db):
        user = UserAccountFactory()
        client.force_login(user)

        response = client.post(
            reverse("account_change_phone"), {"phone": "+919876543210"}
        )
        assert response.status_code == 302

        state = client.session[PHONE_VERIFICATION_SESSION_KEY]
        code = state["code"]

        response = client.post(reverse("account_verify_phone"), {"code": code})
        assert response.status_code == 302

        user.refresh_from_db()
        assert str(user.phone) == "+919876543210"
        assert user.phone_verified is True
