from __future__ import annotations

from django.urls import reverse


class TestAccountURLs:
    def test_phone_verify_url(self):
        url = reverse("account_verify_phone")
        assert url.startswith("/auth/phone/verify/")

    def test_phone_change_url(self):
        url = reverse("account_change_phone")
        assert url.startswith("/auth/phone/change/")
