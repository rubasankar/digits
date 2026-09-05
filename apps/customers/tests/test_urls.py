from __future__ import annotations

from django.urls import reverse


class TestCustomerURLs:
    def test_dashboard_url(self):
        assert reverse("customers:dashboard") == "/account/"

    def test_profile_url(self):
        assert reverse("customers:profile") == "/account/profile/"

    def test_profile_edit_url(self):
        assert reverse("customers:profile_edit") == "/account/profile/edit/"

    def test_addresses_url(self):
        assert reverse("customers:addresses") == "/account/addresses/"

    def test_address_add_url(self):
        assert reverse("customers:address_add") == "/account/addresses/add/"

    def test_security_url(self):
        assert reverse("customers:security") == "/account/security/"

    def test_address_edit_url(self):
        from uuid import uuid4

        url = reverse("customers:address_edit", kwargs={"pk": uuid4()})
        assert url.startswith("/account/addresses/")
        assert url.endswith("/edit/")

    def test_address_delete_url(self):
        from uuid import uuid4

        url = reverse("customers:address_delete", kwargs={"pk": uuid4()})
        assert url.startswith("/account/addresses/")
        assert url.endswith("/delete/")
