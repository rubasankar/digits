from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import messages
from django.http import HttpRequest
from django.http import HttpResponse
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render

from apps.customers.forms import CustomerAddressForm
from apps.customers.forms import CustomerProfileForm
from apps.customers.models import CustomerAddress
from apps.customers.models import CustomerProfile
from apps.customers.service.profile import AddressDeletionError
from apps.customers.service.profile import ProfileService
from apps.orders.service.storefront import OrderStorefrontService
from apps.shopping.models import Wishlist
from apps.shopping.models import WishlistItem
from apps.shopping.service.wishlist import WishlistService
from core.decorators import require_customer

if TYPE_CHECKING:
    from uuid import UUID


def _get_profile(request: HttpRequest) -> CustomerProfile | None:
    """Return the CustomerProfile for the authenticated user, or None."""
    from apps.accounts.models import UserAccount  # noqa: PLC0415

    if not isinstance(request.user, UserAccount):
        return None
    try:
        return CustomerProfile.objects.get(user=request.user)
    except CustomerProfile.DoesNotExist:
        return None


@require_customer
def account_dashboard(request: HttpRequest) -> HttpResponse:
    """Display account dashboard with summary counts."""
    profile = _get_profile(request)
    if profile is None:
        messages.info(request, "Please complete your profile to continue.")
        return redirect("customers:profile_edit")

    address_count = profile.addresses.count()
    order_count = (
        OrderStorefrontService().get_orders_for_customer(profile, page=1).count()
    )
    try:
        wishlist_count = profile.wishlist.items.count()
    except Wishlist.DoesNotExist:
        wishlist_count = 0

    return render(
        request,
        "customers/dashboard.html",
        {
            "address_count": address_count,
            "order_count": order_count,
            "wishlist_count": wishlist_count,
        },
    )


@require_customer
def profile_detail(request: HttpRequest) -> HttpResponse:
    """Display the read-only profile view."""
    profile = _get_profile(request)
    if profile is None:
        return redirect("customers:profile_edit")

    return render(request, "customers/profile.html", {"profile": profile})


@require_customer
def profile_edit(request: HttpRequest) -> HttpResponse:
    """Display and process the profile edit form."""
    profile = _get_profile(request)
    if profile is None:
        # Create a minimal profile so user can fill it in
        profile = CustomerProfile(user=request.user)  # type: ignore[misc]
        profile.first_name = getattr(request.user, "first_name", "") or ""
        profile.last_name = getattr(request.user, "last_name", "") or ""
        profile.save()

    if request.method == "POST":
        form = CustomerProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            ProfileService().update_profile(profile, form.cleaned_data)
            messages.success(request, "Profile updated successfully.")
            return redirect("customers:profile")
    else:
        form = CustomerProfileForm(instance=profile)

    return render(request, "customers/profile_form.html", {"form": form})


@require_customer
def address_list(request: HttpRequest) -> HttpResponse:
    """Display all addresses for the customer."""
    profile = _get_profile(request)
    if profile is None:
        return redirect("customers:profile_edit")

    addresses = ProfileService().list_addresses(profile)
    return render(
        request,
        "customers/addresses/list.html",
        {"addresses": addresses},
    )


@require_customer
def address_add(request: HttpRequest) -> HttpResponse:
    """Add a new address."""
    profile = _get_profile(request)
    if profile is None:
        return redirect("customers:profile_edit")

    if request.method == "POST":
        form = CustomerAddressForm(request.POST)
        if form.is_valid():
            ProfileService().add_address(profile, form.cleaned_data)
            messages.success(request, "Address added.")
            return redirect("customers:addresses")
    else:
        form = CustomerAddressForm()

    return render(
        request,
        "customers/addresses/form.html",
        {"form": form, "is_edit": False, "address": None},
    )


@require_customer
def address_edit(request: HttpRequest, pk: UUID) -> HttpResponse:
    """Edit an existing address."""
    profile = _get_profile(request)
    if profile is None:
        return redirect("customers:profile_edit")

    address = get_object_or_404(CustomerAddress, pk=pk, customer=profile)

    if request.method == "POST":
        form = CustomerAddressForm(request.POST, instance=address)
        if form.is_valid():
            ProfileService().update_address(profile, pk, form.cleaned_data)
            messages.success(request, "Address updated.")
            return redirect("customers:addresses")
    else:
        form = CustomerAddressForm(instance=address)

    return render(
        request,
        "customers/addresses/form.html",
        {"form": form, "is_edit": True, "address": address},
    )


@require_customer
def address_delete(request: HttpRequest, pk: UUID) -> HttpResponse:
    """Delete an address (POST only)."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    profile = _get_profile(request)
    if profile is None:
        return redirect("customers:profile_edit")

    try:
        ProfileService().delete_address(profile, pk)
        messages.success(request, "Address deleted.")
    except AddressDeletionError:
        messages.error(
            request,
            "This address is in use by an active checkout and cannot be deleted.",
        )
    except CustomerAddress.DoesNotExist:
        messages.error(request, "Address not found.")

    return redirect("customers:addresses")


@require_customer
def wishlist_detail(request: HttpRequest) -> HttpResponse:
    """Display the customer's wishlist."""
    profile = _get_profile(request)
    if profile is None:
        wishlist_items = WishlistItem.objects.none()
    else:
        wishlist, _ = WishlistService.get_or_create_wishlist(profile)
        wishlist_items = wishlist.items.select_related("variant").prefetch_related(
            "variant__prices",
            "variant__images",
            "variant__product",
        )

    return render(
        request,
        "customers/wishlist.html",
        {"wishlist_items": wishlist_items},
    )


@require_customer
def wishlist_remove(request: HttpRequest, pk: UUID) -> HttpResponse:
    """Remove an item from the wishlist (POST only)."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    profile = _get_profile(request)
    if profile is not None:
        WishlistItem.objects.filter(pk=pk, wishlist__customer=profile).delete()

    return redirect("customers:wishlist")


@require_customer
def security_overview(request: HttpRequest) -> HttpResponse:
    """Display MFA and security overview."""
    mfa_enabled = False
    social_accounts = []
    phone = None
    phone_verified = False
    try:
        from allauth.mfa.models import Authenticator  # noqa: PLC0415

        mfa_enabled = Authenticator.objects.filter(user=request.user).exists()
    except ImportError:
        pass

    try:
        from allauth.socialaccount.models import SocialAccount  # noqa: PLC0415

        social_accounts = SocialAccount.objects.filter(user=request.user)
    except ImportError:
        pass

    from allauth.account.adapter import get_adapter  # noqa: PLC0415

    phone_result = get_adapter().get_phone(request.user)
    if phone_result is not None:
        phone, phone_verified = phone_result

    return render(
        request,
        "customers/security.html",
        {
            "mfa_enabled": mfa_enabled,
            "social_accounts": social_accounts,
            "phone": phone,
            "phone_verified": phone_verified,
        },
    )


@require_customer
def order_history(request: HttpRequest) -> HttpResponse:
    """Thin redirect to orders:history."""
    return redirect("orders:history")
