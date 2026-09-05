from __future__ import annotations

import pytest

from apps.accounts.tests.factories import UserAccountFactory
from apps.customers.models import CustomerAddress
from apps.customers.models import CustomerProfile


@pytest.fixture
def logged_in_client(client, db):
    user = UserAccountFactory()
    client.force_login(user)
    return client, user


@pytest.mark.django_db
class TestAccountDashboard:
    def test_redirect_without_profile(self, logged_in_client):
        client, _user = logged_in_client
        response = client.get("/account/")
        assert response.status_code == 302

    def test_renders_with_profile(self, logged_in_client):
        client, user = logged_in_client
        CustomerProfile.objects.create(user=user, first_name="Test", last_name="User")
        response = client.get("/account/")
        assert response.status_code == 200


@pytest.mark.django_db
class TestProfileDetail:
    def test_redirect_without_profile(self, logged_in_client):
        client, _user = logged_in_client
        response = client.get("/account/profile/")
        assert response.status_code == 302

    def test_renders_with_profile(self, logged_in_client):
        client, user = logged_in_client
        CustomerProfile.objects.create(user=user, first_name="Test", last_name="User")
        response = client.get("/account/profile/")
        assert response.status_code == 200


@pytest.mark.django_db
class TestProfileEdit:
    def test_redirect_without_profile(self, logged_in_client):
        client, _user = logged_in_client
        response = client.get("/account/profile/edit/")
        assert response.status_code == 200

    def test_post_updates_profile(self, logged_in_client):
        client, user = logged_in_client
        CustomerProfile.objects.create(user=user, first_name="Old", last_name="User")
        response = client.post(
            "/account/profile/edit/",
            data={"first_name": "New", "last_name": "User", "gender": "M"},
        )
        assert response.status_code == 302
        profile = CustomerProfile.objects.get(user=user)
        assert profile.first_name == "New"


@pytest.mark.django_db
class TestAddressList:
    def test_redirect_without_profile(self, logged_in_client):
        client, _user = logged_in_client
        response = client.get("/account/addresses/")
        assert response.status_code == 302

    def test_renders_with_profile(self, logged_in_client):
        client, user = logged_in_client
        CustomerProfile.objects.create(user=user, first_name="Test", last_name="User")
        response = client.get("/account/addresses/")
        assert response.status_code == 200


@pytest.mark.django_db
class TestAddressAdd:
    def test_redirect_without_profile(self, logged_in_client):
        client, _user = logged_in_client
        response = client.get("/account/addresses/add/")
        assert response.status_code == 302

    def test_get_renders(self, logged_in_client):
        client, user = logged_in_client
        CustomerProfile.objects.create(user=user, first_name="Test", last_name="User")
        response = client.get("/account/addresses/add/")
        assert response.status_code == 200

    def test_post_creates_address(self, logged_in_client):
        client, user = logged_in_client
        CustomerProfile.objects.create(user=user, first_name="Test", last_name="User")
        response = client.post(
            "/account/addresses/add/",
            data={
                "full_name": "John Doe",
                "contact_number": "+14155552671",
                "address_type": "BOTH",
                "address_line1": "123 Main St",
                "city": "Springfield",
                "state": "IL",
                "country": "US",
                "pincode": "62701",
            },
        )
        assert response.status_code == 302
        assert CustomerAddress.objects.count() == 1


@pytest.mark.django_db
class TestSecurityOverview:
    def test_renders(self, logged_in_client):
        client, user = logged_in_client
        CustomerProfile.objects.create(user=user, first_name="Test", last_name="User")
        response = client.get("/account/security/")
        assert response.status_code == 200


@pytest.mark.django_db
class TestOrderHistory:
    def test_redirects_to_orders(self, logged_in_client):
        client, user = logged_in_client
        CustomerProfile.objects.create(user=user, first_name="Test", last_name="User")
        response = client.get("/account/orders/")
        assert response.status_code == 302
