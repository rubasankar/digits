from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError

from apps.staff.models import StaffDepartment
from apps.staff.models import StaffProfile
from apps.staff.tests.factories import StaffDepartmentFactory
from apps.staff.tests.factories import StaffProfileFactory


@pytest.mark.django_db
class TestStaffDepartmentModel:
    def test_create(self):
        dept = StaffDepartmentFactory(name="Warehouse")
        assert dept.pk is not None
        assert dept.name == "Warehouse"

    def test_str(self):
        dept = StaffDepartmentFactory(name="Support")
        assert str(dept) == "Support"

    def test_repr(self):
        dept = StaffDepartmentFactory(name="Ops")
        r = repr(dept)
        assert "StaffDepartment" in r

    def test_unique_name(self):
        StaffDepartmentFactory(name="Warehouse")
        with pytest.raises(Exception):
            StaffDepartmentFactory(name="Warehouse")

    def test_ordering(self):
        StaffDepartmentFactory(name="B", display_order=2)
        StaffDepartmentFactory(name="A", display_order=1)
        depts = list(StaffDepartment.objects.all())
        assert depts[0].name == "A"
        assert depts[1].name == "B"

    def test_default_active(self):
        dept = StaffDepartmentFactory()
        assert dept.is_active is True


@pytest.mark.django_db
class TestStaffProfileModel:
    def test_create(self):
        profile = StaffProfileFactory()
        assert profile.pk is not None

    def test_str_with_role(self):
        profile = StaffProfileFactory(
            first_name="Jane", last_name="Doe", role="Manager"
        )
        assert str(profile) == "Jane Doe (Manager)"

    def test_str_without_role(self):
        profile = StaffProfileFactory(first_name="Jane", last_name="Doe", role="")
        assert str(profile) == "Jane Doe"

    def test_repr(self):
        profile = StaffProfileFactory()
        r = repr(profile)
        assert "StaffProfile" in r

    def test_full_name(self):
        profile = StaffProfileFactory(first_name="Jane", last_name="Doe")
        assert profile.full_name == "Jane Doe"

    def test_display_name_with_role(self):
        profile = StaffProfileFactory(first_name="Jane", last_name="Doe", role="Agent")
        assert profile.display_name == "Jane Doe (Agent)"

    def test_display_name_without_role(self):
        profile = StaffProfileFactory(first_name="Jane", last_name="Doe", role="")
        assert profile.display_name == "Jane Doe"

    def test_clean_valid(self):
        profile = StaffProfileFactory()
        profile.clean()

    def test_clean_user_not_staff_raises(self):
        from apps.accounts.tests.factories import UserAccountFactory

        user = UserAccountFactory(is_staff=False)
        profile = StaffProfile(user=user, first_name="Test")
        with pytest.raises(ValidationError) as exc_info:
            profile.clean()
        assert "is_staff=True" in str(exc_info.value)

    def test_one_to_one_user(self):
        from apps.accounts.tests.factories import StaffUserFactory

        user = StaffUserFactory()
        StaffProfile.objects.create(user=user, first_name="Staff")
        assert hasattr(user, "staff_profile")

    def test_department_set_null(self):
        dept = StaffDepartmentFactory()
        profile = StaffProfileFactory(department=dept)
        dept.delete()
        profile.refresh_from_db()
        assert profile.department is None
