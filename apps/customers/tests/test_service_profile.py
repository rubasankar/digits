from __future__ import annotations

import pytest

from apps.accounts.tests.factories import UserAccountFactory
from apps.customers.models import CustomerAddress
from apps.customers.models import CustomerProfile
from apps.customers.service.profile import AddressInput
from apps.customers.service.profile import CustomerService
from apps.customers.service.profile import ProfileService
from apps.customers.tests.factories import CustomerAddressFactory
from apps.customers.tests.factories import CustomerProfileFactory


@pytest.mark.django_db
class TestCustomerService:
    def test_get_or_create_profile_creates(self):

        user = UserAccountFactory()
        profile, created = CustomerService.get_or_create_profile(
            user, first_name="John", last_name="Doe"
        )
        assert created is True
        assert profile.first_name == "John"

    def test_get_or_create_profile_gets_existing(self):

        user = UserAccountFactory()
        existing = CustomerProfile.objects.create(
            user=user, first_name="Existing", last_name="Profile"
        )
        profile, created = CustomerService.get_or_create_profile(
            user, first_name="New", last_name="Name"
        )
        assert created is False
        assert profile.pk == existing.pk

    def test_snapshot_address(self):
        address = CustomerAddressFactory(
            full_name="John Doe",
            contact_number="+14155552671",
            address_line1="123 Main St",
            city="Springfield",
            state="IL",
            country="US",
            pincode="62701",
        )
        snapshot = CustomerService.snapshot_address(address)
        assert snapshot["full_name"] == "John Doe"
        assert snapshot["city"] == "Springfield"

    def test_add_address(self):
        profile = CustomerProfileFactory()
        data = AddressInput(
            full_name="John Doe",
            contact_number="+14155552671",
            address_line1="123 Main St",
            city="Springfield",
            state="IL",
            country="US",
            pincode="62701",
        )
        address = CustomerService.add_address(profile, data=data)
        assert address.pk is not None


@pytest.mark.django_db
class TestProfileService:
    def test_update_profile(self):
        profile = CustomerProfileFactory(first_name="Old")
        service = ProfileService()
        result = service.update_profile(profile, {"first_name": "New"})
        result.refresh_from_db()
        assert result.first_name == "New"

    def test_list_addresses(self):
        profile = CustomerProfileFactory()
        CustomerAddressFactory(customer=profile, is_default=True)
        CustomerAddressFactory(customer=profile, is_default=False)
        service = ProfileService()
        addresses = service.list_addresses(profile)
        assert addresses.count() == 2

    def test_add_address(self):
        profile = CustomerProfileFactory()
        service = ProfileService()
        data = {
            "full_name": "John Doe",
            "contact_number": "+14155552671",
            "address_line1": "123 Main St",
            "city": "Springfield",
            "state": "IL",
            "country": "US",
            "pincode": "62701",
            "is_default": False,
        }
        address = service.add_address(profile, data)
        assert address.pk is not None

    def test_delete_address(self):
        profile = CustomerProfileFactory()
        addr = CustomerAddressFactory(customer=profile)
        service = ProfileService()
        service.delete_address(profile, addr.pk)
        assert not CustomerAddress.objects.filter(pk=addr.pk).exists()
