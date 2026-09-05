from __future__ import annotations

import pytest

from apps.accounts.tests.factories import StaffUserFactory
from apps.accounts.tests.factories import SuperUserFactory
from apps.staff.admin import StaffProfileAdmin
from apps.staff.models import StaffProfile
from apps.staff.tests.factories import StaffProfileFactory


@pytest.fixture
def admin_user(db):
    return SuperUserFactory()


@pytest.fixture
def staff_user(db):
    return StaffUserFactory()


@pytest.mark.django_db
class TestStaffProfileAdminPermissions:
    def test_superuser_has_view_permission(self, admin_user):
        from unittest.mock import MagicMock

        admin = StaffProfileAdmin(StaffProfile, None)
        request = MagicMock()
        request.user = admin_user
        assert admin.has_view_permission(request) is True

    def test_staff_user_has_view_permission_own_profile(self, staff_user):
        from unittest.mock import MagicMock

        admin = StaffProfileAdmin(StaffProfile, None)
        request = MagicMock()
        request.user = staff_user
        profile = StaffProfileFactory(user=staff_user)
        assert admin.has_view_permission(request, profile) is True

    def test_staff_user_no_view_permission_other_profile(self, staff_user):
        from unittest.mock import MagicMock

        admin = StaffProfileAdmin(StaffProfile, None)
        request = MagicMock()
        request.user = staff_user
        other_profile = StaffProfileFactory()
        assert admin.has_view_permission(request, other_profile) is False

    def test_superuser_has_add_permission(self, admin_user):
        from unittest.mock import MagicMock

        admin = StaffProfileAdmin(StaffProfile, None)
        request = MagicMock()
        request.user = admin_user
        assert admin.has_add_permission(request) is True

    def test_staff_user_no_add_permission(self, staff_user):
        from unittest.mock import MagicMock

        admin = StaffProfileAdmin(StaffProfile, None)
        request = MagicMock()
        request.user = staff_user
        assert admin.has_add_permission(request) is False

    def test_superuser_has_delete_permission(self, admin_user):
        from unittest.mock import MagicMock

        admin = StaffProfileAdmin(StaffProfile, None)
        request = MagicMock()
        request.user = admin_user
        assert admin.has_delete_permission(request) is True

    def test_staff_user_no_delete_permission(self, staff_user):
        from unittest.mock import MagicMock

        admin = StaffProfileAdmin(StaffProfile, None)
        request = MagicMock()
        request.user = staff_user
        assert admin.has_delete_permission(request) is False


@pytest.mark.django_db
class TestStaffProfileAdminQueryset:
    def test_superuser_sees_all(self, admin_user):
        from unittest.mock import MagicMock

        admin = StaffProfileAdmin(StaffProfile, None)
        request = MagicMock()
        request.user = admin_user
        StaffProfileFactory()
        StaffProfileFactory()
        qs = admin.get_queryset(request)
        assert qs.count() == 2

    def test_staff_sees_own_only(self, staff_user):
        from unittest.mock import MagicMock

        admin = StaffProfileAdmin(StaffProfile, None)
        request = MagicMock()
        request.user = staff_user
        StaffProfileFactory(user=staff_user)
        StaffProfileFactory()
        qs = admin.get_queryset(request)
        assert qs.count() == 1


@pytest.mark.django_db
class TestStaffProfileAdminFieldsets:
    def test_superuser_gets_full_fieldsets(self, admin_user):
        from unittest.mock import MagicMock

        admin = StaffProfileAdmin(StaffProfile, None)
        request = MagicMock()
        request.user = admin_user
        fieldsets = admin.get_fieldsets(request)
        field_names = [f for _, f in fieldsets for f in f.get("fields", [])]
        assert "is_active" in field_names

    def test_staff_gets_self_service_fieldsets(self, staff_user):
        from unittest.mock import MagicMock

        admin = StaffProfileAdmin(StaffProfile, None)
        request = MagicMock()
        request.user = staff_user
        fieldsets = admin.get_fieldsets(request)
        assert fieldsets == StaffProfileAdmin.SELF_SERVICE_FIELDSETS


@pytest.mark.django_db
class TestStaffProfileAdminAvatarDisplay:
    def test_no_avatar(self):

        admin = StaffProfileAdmin(StaffProfile, None)
        profile = StaffProfileFactory()
        result = admin.avatar_display(profile)
        assert "no avatar" in result.lower()


@pytest.mark.django_db
class TestStaffDepartmentAdmin:
    def test_list_display(self):
        from apps.staff.admin import StaffDepartmentAdmin

        assert "name" in StaffDepartmentAdmin.list_display
        assert "is_active" in StaffDepartmentAdmin.list_display
