from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.db import transaction
from django.utils.translation import gettext_lazy as _

from core.enums import AddressChoices
from core.exceptions import NotFoundError

from .models import CustomerAddress
from .models import CustomerProfile

if TYPE_CHECKING:
    from uuid import UUID

    from apps.accounts.models import UserAccount


@dataclass(frozen=True, slots=True)
class AddressInput:
    """Customer-supplied fields for a new postal address."""

    full_name: str
    contact_number: str
    address_line1: str
    city: str
    state: str
    country: str
    pincode: str
    address_line2: str = ""
    landmark: str = ""
    address_type: str = AddressChoices.BOTH


class CustomerService:
    # Profile lifecycle

    @classmethod
    @transaction.atomic
    def get_or_create_profile(
        cls,
        user: UserAccount,
        *,
        first_name: str = "",
        last_name: str = "",
    ) -> tuple[CustomerProfile, bool]:
        try:
            profile = CustomerProfile.objects.get(user=user)
        except CustomerProfile.DoesNotExist:
            pass
        else:
            return profile, False

        profile = CustomerProfile(
            user=user,
            first_name=first_name or getattr(user, "first_name", "") or "",
            last_name=last_name or getattr(user, "last_name", "") or "",
        )
        profile.full_clean()
        profile.save()
        return profile, True

    # Address management

    @classmethod
    @transaction.atomic
    def set_default_address(cls, address: CustomerAddress) -> CustomerAddress:
        # Lock the current default for this customer / type (if any).
        existing = (
            CustomerAddress.objects.select_for_update()
            .filter(
                customer=address.customer,
                address_type=address.address_type,
                is_default=True,
            )
            .exclude(pk=address.pk)
            .first()
        )

        if existing is not None:
            existing.is_default = False
            existing.save(update_fields=["is_default"])

        address.is_default = True
        if address.pk:
            address.save(update_fields=["is_default"])
        else:
            address.full_clean()
            address.save()

        return address

    @classmethod
    def get_default_address(
        cls,
        profile: CustomerProfile,
        address_type: str,
    ) -> CustomerAddress | None:
        # A BOTH address satisfies both shipping and billing queries.
        compatible_types = {address_type, AddressChoices.BOTH}

        return (
            CustomerAddress.objects.filter(
                customer=profile,
                address_type__in=compatible_types,
                is_default=True,
            )
            .order_by("-created")  # BOTH wins over specific when both exist
            .first()
        )

    @classmethod
    def snapshot_address(cls, address: CustomerAddress) -> dict[str, str]:
        return {
            "full_name": address.full_name,
            "contact_number": str(address.contact_number),
            "address_line1": address.address_line1,
            "address_line2": address.address_line2,
            "landmark": address.landmark,
            "city": address.city,
            "state": address.state,
            "country": str(address.country),
            "pincode": address.pincode,
        }

    @classmethod
    @transaction.atomic
    def add_address(
        cls,
        profile: CustomerProfile,
        *,
        data: AddressInput,
        set_as_default: bool = False,
    ) -> CustomerAddress:
        address = CustomerAddress(
            customer=profile,
            full_name=data.full_name,
            contact_number=data.contact_number,
            address_line1=data.address_line1,
            address_line2=data.address_line2,
            landmark=data.landmark,
            city=data.city,
            state=data.state,
            country=data.country,
            pincode=data.pincode,
            address_type=data.address_type,
            is_default=False,
        )
        address.full_clean()
        address.save()

        if set_as_default:
            cls.set_default_address(address)

        return address

    @classmethod
    def get_address_or_raise(
        cls,
        profile: CustomerProfile,
        address_pk: UUID,
    ) -> CustomerAddress:
        try:
            return CustomerAddress.objects.get(pk=address_pk, customer=profile)
        except CustomerAddress.DoesNotExist as err:
            raise NotFoundError(_("Address not found for this customer.") % {}) from err
