from __future__ import annotations

import pytest

from apps.customers.models import CustomerProfile
from apps.customers.tests.factories import CustomerAddressFactory
from apps.customers.tests.factories import CustomerProfileFactory


@pytest.mark.django_db
class TestCustomerProfileModel:
    def test_create(self):
        profile = CustomerProfileFactory()
        assert profile.pk is not None

    def test_full_name(self):
        profile = CustomerProfileFactory(first_name="John", last_name="Doe")
        assert profile.full_name == "John Doe"

    def test_full_name_stripped(self):
        profile = CustomerProfileFactory(first_name="John", last_name="")
        assert profile.full_name == "John"

    def test_str_with_name(self):
        profile = CustomerProfileFactory(first_name="John", last_name="Doe")
        assert str(profile) == "John Doe"

    def test_str_fallback_to_email(self):
        from apps.accounts.tests.factories import UserAccountFactory

        user = UserAccountFactory(email="user@example.com")
        profile = CustomerProfile.objects.create(user=user, first_name="")
        assert str(profile) == "user@example.com"

    def test_repr(self):
        profile = CustomerProfileFactory()
        r = repr(profile)
        assert "CustomerProfile" in r

    def test_one_to_one_user(self):
        from apps.accounts.tests.factories import UserAccountFactory

        user = UserAccountFactory()
        CustomerProfile.objects.create(user=user, first_name="Test")
        assert hasattr(user, "customer_profile")


@pytest.mark.django_db
class TestCustomerAddressModel:
    def test_create(self):
        address = CustomerAddressFactory()
        assert address.pk is not None

    def test_str_with_default(self):
        address = CustomerAddressFactory(
            full_name="John Doe",
            city="Springfield",
            country="US",
            is_default=True,
        )
        result = str(address)
        assert "John Doe" in result
        assert "Springfield" in result
        assert "(default)" in result

    def test_str_without_default(self):
        address = CustomerAddressFactory(
            full_name="John Doe",
            city="Springfield",
            country="US",
            is_default=False,
        )
        result = str(address)
        assert "(default)" not in result

    def test_repr(self):
        address = CustomerAddressFactory()
        r = repr(address)
        assert "UserAddress" in r
