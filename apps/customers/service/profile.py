from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Any

from django.db import transaction
from django.utils.translation import gettext_lazy as _

from apps.customers.models import CustomerAddress
from apps.customers.models import CustomerProfile
from core.enums import AddressChoices
from core.exceptions import NotFoundError

if TYPE_CHECKING:
    from uuid import UUID

    from django.db.models import QuerySet

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


class AddressDeletionError(Exception):
    """Raised when an address cannot be deleted because it is in active use."""


def _conflicting_default_types(address_type: str) -> set[str]:
    """Address types whose 'default' flag conflicts with a default of address_type.

    A BOTH-type default serves as the default for both SHIP and BILL roles, so
    it conflicts with an existing default of either type (and vice versa); a
    SHIP/BILL default only conflicts with a default of the same type or BOTH.
    """
    if address_type == AddressChoices.BOTH:
        return {AddressChoices.SHIPPING, AddressChoices.BILLING, AddressChoices.BOTH}
    return {address_type, AddressChoices.BOTH}


class CustomerService:
    """Utility methods for customer profile and address management."""

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
        """Get or create a CustomerProfile for the given user."""
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
        """Make address the default for its type; unset any conflicting default."""
        conflicting_types = _conflicting_default_types(address.address_type)
        existing = (
            CustomerAddress.objects.select_for_update()
            .filter(
                customer=address.customer,
                address_type__in=conflicting_types,
                is_default=True,
            )
            .exclude(pk=address.pk)
        )

        for other in existing:
            other.is_default = False
            other.save(update_fields=["is_default"])

        address.is_default = True
        address.full_clean()
        address.save()

        return address

    @classmethod
    def get_default_address(
        cls,
        profile: CustomerProfile,
        address_type: str,
    ) -> CustomerAddress | None:
        """Return the default address for a given type, or None."""
        compatible_types = {address_type, AddressChoices.BOTH}

        return (
            CustomerAddress.objects.filter(
                customer=profile,
                address_type__in=compatible_types,
                is_default=True,
            )
            .order_by("-created")
            .first()
        )

    @classmethod
    def snapshot_address(cls, address: CustomerAddress) -> dict[str, str]:
        """Return a plain-dict snapshot of address fields for order records."""
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
        """Create and optionally set as default a new address for a profile."""
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
        """Return address by pk/customer or raise NotFoundError."""
        try:
            return CustomerAddress.objects.get(pk=address_pk, customer=profile)
        except CustomerAddress.DoesNotExist as err:
            raise NotFoundError(_("Address not found for this customer.") % {}) from err


class ProfileService:
    """Storefront-facing service for customer profile and address management."""

    @transaction.atomic
    def update_profile(
        self,
        customer: CustomerProfile,
        data: dict[str, Any],
    ) -> CustomerProfile:
        """Update allowed CustomerProfile fields from a validated dict."""
        allowed = {
            "first_name",
            "last_name",
            "phone_number",
            "date_of_birth",
            "gender",
            "avatar",
            "accepts_marketing",
        }
        for field, value in data.items():
            if field in allowed:
                setattr(customer, field, value)
        customer.full_clean()
        customer.save()
        return customer

    def list_addresses(
        self,
        customer: CustomerProfile,
    ) -> QuerySet[CustomerAddress]:
        """Return all addresses for a customer, defaults first."""
        return customer.addresses.order_by("-is_default", "-created")

    @transaction.atomic
    def add_address(
        self,
        customer: CustomerProfile,
        data: dict[str, Any],
    ) -> CustomerAddress:
        """Create a new address. Unset any conflicting default if is_default=True."""
        address = CustomerAddress(customer=customer, **data)
        if address.is_default:
            return CustomerService.set_default_address(address)
        address.full_clean()
        address.save()
        return address

    @transaction.atomic
    def update_address(
        self,
        customer: CustomerProfile,
        address_id: UUID,
        data: dict[str, Any],
    ) -> CustomerAddress:
        """Update an existing address."""
        address = CustomerAddress.objects.get(pk=address_id, customer=customer)
        for field, value in data.items():
            setattr(address, field, value)
        if address.is_default:
            return CustomerService.set_default_address(address)
        address.full_clean()
        address.save()
        return address

    @transaction.atomic
    def delete_address(
        self,
        customer: CustomerProfile,
        address_id: UUID,
    ) -> None:
        """
        Delete an address.
        Raises AddressDeletionError if referenced by an active CheckoutSession.
        """
        from apps.checkout.enums import SessionStatus  # noqa: PLC0415

        address = CustomerAddress.objects.get(pk=address_id, customer=customer)
        active_statuses = [SessionStatus.ACTIVE, SessionStatus.PROCESSING]
        in_use = (
            address.shipping_checkout_sessions.filter(
                status__in=active_statuses
            ).exists()
            or address.billing_checkout_sessions.filter(
                status__in=active_statuses
            ).exists()
        )
        if in_use:
            msg = "This address is in use by an active checkout and cannot be deleted."
            raise AddressDeletionError(msg)
        address.delete()
