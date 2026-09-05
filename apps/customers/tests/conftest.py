from __future__ import annotations

import pytest

from apps.customers.tests.factories import CustomerAddressFactory
from apps.customers.tests.factories import CustomerProfileFactory


@pytest.fixture
def customer_profile(db):
    return CustomerProfileFactory()


@pytest.fixture
def customer_address(db, customer_profile):
    return CustomerAddressFactory(customer=customer_profile)
