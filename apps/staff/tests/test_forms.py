from __future__ import annotations

import pytest

from apps.staff.forms import StaffProfileForm
from apps.staff.tests.factories import StaffProfileFactory


@pytest.mark.django_db
class TestStaffProfileForm:
    def test_valid(self):
        profile = StaffProfileFactory()
        form = StaffProfileForm(
            data={"first_name": "Jane", "last_name": "Doe"},
            instance=profile,
        )
        assert form.is_valid(), form.errors

    def test_fields(self):
        form = StaffProfileForm()
        expected = {"first_name", "last_name", "avatar"}
        assert set(form.fields) == expected
