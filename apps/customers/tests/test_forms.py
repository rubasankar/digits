from __future__ import annotations

import datetime
import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.customers.forms import CustomerAddressForm
from apps.customers.forms import CustomerProfileForm
from apps.customers.forms import MarketingPreferenceForm

_FORMAT_MAP = {
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
    "image/gif": "GIF",
}


def _make_image(content_type: str, *, size: tuple[int, int] = (10, 10)) -> bytes:
    fmt = _FORMAT_MAP[content_type]
    img = Image.new("RGB", size, color="red")
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def _make_large_image() -> bytes:
    img = Image.new("RGB", (10, 10), color="red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    jpeg_bytes = buf.getvalue()
    return jpeg_bytes + b"\x00" * (5 * 1024 * 1024 + 1 - len(jpeg_bytes))


@pytest.mark.django_db
class TestCustomerProfileForm:
    def test_valid(self):
        form = CustomerProfileForm(
            data={
                "first_name": "John",
                "last_name": "Doe",
                "date_of_birth": "1990-01-01",
                "gender": "M",
                "accepts_marketing": True,
            }
        )
        assert form.is_valid(), form.errors

    def test_dob_future_date(self):
        form = CustomerProfileForm(
            data={
                "first_name": "John",
                "last_name": "Doe",
                "date_of_birth": "2030-01-01",
                "gender": "M",
            }
        )
        assert not form.is_valid()
        assert "date_of_birth" in form.errors

    def test_dob_too_young(self):
        today = datetime.date.today()
        young_dob = datetime.date(today.year - 10, today.month, today.day)
        form = CustomerProfileForm(
            data={
                "first_name": "John",
                "last_name": "Doe",
                "date_of_birth": young_dob.isoformat(),
                "gender": "M",
            }
        )
        assert not form.is_valid()
        assert "date_of_birth" in form.errors

    def test_dob_exactly_13(self):
        today = datetime.date.today()
        dob_13 = datetime.date(today.year - 13, today.month, today.day)
        form = CustomerProfileForm(
            data={
                "first_name": "John",
                "last_name": "Doe",
                "date_of_birth": dob_13.isoformat(),
                "gender": "M",
            }
        )
        assert form.is_valid(), form.errors

    def test_avatar_too_large(self):
        large_avatar = SimpleUploadedFile(
            name="large.jpg",
            content=_make_large_image(),
            content_type="image/jpeg",
        )
        form = CustomerProfileForm(
            data={"first_name": "John", "last_name": "Doe", "gender": "M"},
            files={"avatar": large_avatar},
        )
        assert not form.is_valid()
        assert "avatar" in form.errors

    def test_avatar_wrong_type(self):
        bad_avatar = SimpleUploadedFile(
            name="file.gif",
            content=_make_image("image/gif"),
            content_type="image/gif",
        )
        form = CustomerProfileForm(
            data={"first_name": "John", "last_name": "Doe", "gender": "M"},
            files={"avatar": bad_avatar},
        )
        assert not form.is_valid()
        assert "avatar" in form.errors

    def test_avatar_valid_types(self):
        for content_type in ["image/jpeg", "image/png", "image/webp"]:
            avatar = SimpleUploadedFile(
                name="avatar.jpg",
                content=_make_image(content_type),
                content_type=content_type,
            )
            form = CustomerProfileForm(
                data={"first_name": "John", "last_name": "Doe", "gender": "M"},
                files={"avatar": avatar},
            )
            assert form.is_valid(), f"Failed for {content_type}: {form.errors}"


@pytest.mark.django_db
class TestMarketingPreferenceForm:
    def test_valid(self):
        form = MarketingPreferenceForm(data={"accepts_marketing": True})
        assert form.is_valid(), form.errors


@pytest.mark.django_db
class TestCustomerAddressForm:
    def test_valid(self):
        form = CustomerAddressForm(
            data={
                "full_name": "John Doe",
                "contact_number": "+14155552671",
                "address_type": "BOTH",
                "address_line1": "123 Main St",
                "city": "Springfield",
                "state": "IL",
                "country": "US",
                "pincode": "62701",
                "is_default": False,
            }
        )
        assert form.is_valid(), form.errors

    def test_missing_required(self):
        form = CustomerAddressForm(data={})
        assert not form.is_valid()
        assert "full_name" in form.errors
