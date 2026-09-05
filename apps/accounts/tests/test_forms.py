from __future__ import annotations

import pytest

from apps.accounts.forms import UserAdminChangeForm
from apps.accounts.forms import UserAdminCreationForm
from apps.accounts.forms import UserSignupForm
from apps.accounts.tests.factories import UserAccountFactory


@pytest.mark.django_db
class TestUserAdminChangeForm:
    def test_valid(self):
        user = UserAccountFactory()
        form = UserAdminChangeForm(
            data={
                "email": "new@example.com",
                "last_login": user.last_login.isoformat() if user.last_login else "",
                "date_joined": user.date_joined.isoformat(),
                "is_active": user.is_active,
                "is_staff": user.is_staff,
                "is_superuser": user.is_superuser,
            },
            instance=user,
        )
        assert form.is_valid(), form.errors

    def test_fields(self):
        form = UserAdminChangeForm()
        assert "email" in form.fields


@pytest.mark.django_db
class TestUserAdminCreationForm:
    def test_valid(self):
        form = UserAdminCreationForm(
            data={
                "email": "test@example.com",
                "password1": "ComplexPass123!",
                "password2": "ComplexPass123!",
            }
        )
        assert form.is_valid(), form.errors

    def test_password_mismatch(self):
        form = UserAdminCreationForm(
            data={
                "email": "test@example.com",
                "password1": "ComplexPass123!",
                "password2": "DifferentPass123!",
            }
        )
        assert not form.is_valid()
        assert "password2" in form.errors


@pytest.mark.django_db
class TestUserSignupForm:
    def test_valid(self):
        form = UserSignupForm(
            data={
                "email": "test@example.com",
                "password1": "ComplexPass123!",
                "password2": "ComplexPass123!",
            }
        )
        assert form.is_valid(), form.errors

    def test_email_required(self):
        form = UserSignupForm(
            data={
                "password1": "ComplexPass123!",
                "password2": "ComplexPass123!",
            }
        )
        assert not form.is_valid()
        assert "email" in form.errors

    def test_password_mismatch(self):
        form = UserSignupForm(
            data={
                "email": "test@example.com",
                "password1": "ComplexPass123!",
                "password2": "DifferentPass123!",
            }
        )
        assert not form.is_valid()
        assert "password2" in form.errors
