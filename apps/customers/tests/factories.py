from __future__ import annotations

import factory

from apps.accounts.tests.factories import UserAccountFactory
from apps.customers.enums import GenderChoices
from apps.customers.models import CustomerAddress
from apps.customers.models import CustomerProfile
from core.enums import AddressChoices


class CustomerProfileFactory(factory.django.DjangoModelFactory):  # type: ignore[type-arg]
    class Meta:
        model = CustomerProfile

    user = factory.SubFactory(UserAccountFactory)  # type: ignore[attr-defined]
    first_name = "Test"
    last_name = "Customer"
    gender = GenderChoices.PREFER_NOT_TO_SAY
    accepts_marketing = False


class CustomerAddressFactory(factory.django.DjangoModelFactory):  # type: ignore[type-arg]
    class Meta:
        model = CustomerAddress

    customer = factory.SubFactory(CustomerProfileFactory)  # type: ignore[attr-defined]
    full_name = "Test User"
    contact_number = "+14155552671"
    address_line1 = "123 Main St"
    city = "Springfield"
    state = "IL"
    country = "US"
    pincode = "62701"
    address_type = AddressChoices.BOTH
    is_default = False
