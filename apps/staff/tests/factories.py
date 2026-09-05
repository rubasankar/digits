from __future__ import annotations

import factory

from apps.accounts.tests.factories import StaffUserFactory
from apps.staff.models import StaffDepartment
from apps.staff.models import StaffProfile


class StaffDepartmentFactory(factory.django.DjangoModelFactory):  # type: ignore[type-arg]
    class Meta:
        model = StaffDepartment

    name = factory.Sequence(lambda n: f"Department {n}")  # type: ignore[attr-defined]
    description = "Test department"
    is_active = True
    display_order = 0


class StaffProfileFactory(factory.django.DjangoModelFactory):  # type: ignore[type-arg]
    class Meta:
        model = StaffProfile

    user = factory.SubFactory(StaffUserFactory)  # type: ignore[attr-defined]
    first_name = "Staff"
    last_name = "Member"
    role = "Manager"
    department = factory.SubFactory(StaffDepartmentFactory)  # type: ignore[attr-defined]
    is_active = True
