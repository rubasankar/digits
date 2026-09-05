from __future__ import annotations

import pytest

from apps.staff.tests.factories import StaffDepartmentFactory
from apps.staff.tests.factories import StaffProfileFactory


@pytest.fixture
def department(db):
    return StaffDepartmentFactory()


@pytest.fixture
def staff_profile(db, department):
    return StaffProfileFactory(department=department)
