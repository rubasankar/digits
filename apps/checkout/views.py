from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _

from apps.checkout.decorators import require_checkout_step
from apps.checkout.enums import CheckoutStep
from apps.checkout.service.checkout import _STEP_URL_MAP
from apps.checkout.service.checkout import CheckoutIncompleteError
from apps.checkout.service.checkout import CheckoutService
from apps.checkout.service.checkout import build_step_context
from apps.customers.forms import CustomerAddressForm
from apps.customers.models import CustomerAddress
from apps.shipping.models import ShippingMethod
from apps.shopping.service.cart import CartService
from core.decorators import require_customer
from core.exceptions import CheckoutAlreadyCompletedError
from core.exceptions import CheckoutSessionExpiredError
from core.exceptions import EmptyCartError

if TYPE_CHECKING:
    from django.http import HttpRequest
    from django.http import HttpResponse

    from apps.checkout.models import CheckoutSession as CheckoutSessionType
    from apps.customers.models import CustomerProfile


def _get_customer_profile(
    request: HttpRequest,
) -> CustomerProfile | None:
    """Return the authenticated user's CustomerProfile or None."""
    try:
        return request.user.customer_profile  # type: ignore[union-attr]
    except AttributeError:
        return None


@login_required(login_url="account_login")
def checkout_start(request: HttpRequest) -> HttpResponse:
    """Create or resume a checkout session and redirect to current step."""
    cart = CartService().get_or_create_cart(request)

    try:
        session = CheckoutService.get_or_create_session(cart)
    except EmptyCartError:
        messages.info(request, str(_("Your cart is empty.")))
        return redirect("shopping:cart")
    except CheckoutAlreadyCompletedError:
        messages.info(request, str(_("That checkout is already completed.")))
        return redirect("shopping:cart")

    step_url = _STEP_URL_MAP.get(CheckoutStep(session.step), "checkout:address")
    return redirect(step_url)


@require_customer
@require_checkout_step(CheckoutStep.ADDRESS)
def checkout_address(
    request: HttpRequest,
    *,
    session: CheckoutSessionType,
) -> HttpResponse:
    """Step 1 -- select or enter a shipping address."""
    customer = _get_customer_profile(request)
    if customer is None:
        return redirect("shopping:cart")

    saved_addresses = CustomerAddress.objects.filter(customer=customer).order_by(
        "-is_default", "-created"
    )
    address_forms = [
        {"address": addr, "form": CustomerAddressForm(instance=addr)}
        for addr in saved_addresses
    ]

    error: str = ""
    if request.method == "POST":
        use_new = request.POST.get("use_new", "")
        if use_new:
            form = CustomerAddressForm(request.POST)
            if form.is_valid():
                address = form.save(commit=False)
                address.customer = customer
                address.save()
                billing_id = request.POST.get("billing_address_id") or None
                billing: CustomerAddress | None = None
                if billing_id:
                    billing = CustomerAddress.objects.filter(
                        pk=billing_id, customer=customer
                    ).first()
                CheckoutService.set_address(
                    session,
                    shipping_address=address,
                    billing_address=billing or address,
                )
                return redirect("checkout:shipping")
            error = str(_("Please correct the errors below."))
        else:
            address_id = request.POST.get("address_id", "")
            selected = CustomerAddress.objects.filter(
                pk=address_id, customer=customer
            ).first()
            if selected is None:
                error = str(_("Please select a valid address."))
            else:
                billing_id = request.POST.get("billing_address_id") or None
                billing = None
                if billing_id:
                    billing = CustomerAddress.objects.filter(
                        pk=billing_id, customer=customer
                    ).first()
                CheckoutService.set_address(
                    session,
                    shipping_address=selected,
                    billing_address=billing or selected,
                )
                return redirect("checkout:shipping")

    new_address_form = CustomerAddressForm()
    context: dict[str, object] = {
        "saved_addresses": saved_addresses,
        "address_forms": address_forms,
        "new_address_form": new_address_form,
        "error": error,
        **build_step_context(session),
    }
    return render(request, "checkout/address.html", context)


@require_customer
@require_checkout_step(CheckoutStep.ADDRESS)
def checkout_edit_address(
    request: HttpRequest,
    *,
    session: CheckoutSessionType,
    pk: object,
) -> HttpResponse:
    """Edit an existing address from within the checkout flow."""
    customer = _get_customer_profile(request)
    if customer is None:
        return redirect("shopping:cart")

    address = get_object_or_404(CustomerAddress, pk=UUID(str(pk)), customer=customer)

    if request.method == "POST":
        form = CustomerAddressForm(request.POST, instance=address)
        if form.is_valid():
            form.save()
            messages.success(request, str(_("Address updated.")))
            return redirect("checkout:address")
    return redirect("checkout:address")


@require_customer
@require_checkout_step(CheckoutStep.SHIPPING)
def checkout_shipping(
    request: HttpRequest,
    *,
    session: CheckoutSessionType,
) -> HttpResponse:
    """Step 2 -- select a shipping method."""
    available_methods = ShippingMethod.objects.filter(is_active=True).order_by("name")

    error: str = ""
    if request.method == "POST":
        method_id = request.POST.get("shipping_method_id", "")
        method = ShippingMethod.objects.filter(pk=method_id, is_active=True).first()
        if method is None:
            error = str(_("Please select a valid shipping method."))
        else:
            CheckoutService.set_shipping_method(
                session,
                method.name,
                method.base_rate,
            )
            return redirect("checkout:payment")

    context: dict[str, object] = {
        "available_methods": available_methods,
        "error": error,
        **build_step_context(session),
    }
    return render(request, "checkout/shipping.html", context)


@require_customer
@require_checkout_step(CheckoutStep.PAYMENT)
def checkout_payment(
    request: HttpRequest,
    *,
    session: CheckoutSessionType,
) -> HttpResponse:
    """Step 3 -- billing address and payment."""
    customer = _get_customer_profile(request)
    if customer is None:
        return redirect("shopping:cart")

    saved_addresses = CustomerAddress.objects.filter(customer=customer).order_by(
        "-is_default", "-created"
    )

    error: str = ""
    if request.method == "POST":
        billing_id = request.POST.get("billing_address_id", "")
        billing = CustomerAddress.objects.filter(
            pk=billing_id, customer=customer
        ).first()
        if billing is None:
            billing = session.shipping_address

        if billing is None:
            error = "Select a billing address to continue."
        else:
            CheckoutService.set_billing_address(session, billing_address=billing)
            return redirect("checkout:review")

    context: dict[str, object] = {
        "saved_addresses": saved_addresses,
        "error": error,
        **build_step_context(session),
    }
    return render(request, "checkout/payment.html", context)


@require_customer
@require_checkout_step(CheckoutStep.CONFIRMATION)
def checkout_review(
    request: HttpRequest,
    *,
    session: CheckoutSessionType,
) -> HttpResponse:
    """Step 4 -- order review and final confirmation."""
    cart = session.cart
    items = cart.items.select_related("variant__product").prefetch_related(
        "variant__images",
        "variant__prices",
    )

    error: str = ""
    if request.method == "POST":
        try:
            order = CheckoutService.complete(session)
        except CheckoutIncompleteError:
            error = str(
                _(
                    "Your checkout is missing required information. "
                    "Please review all steps."
                )
            )
        except CheckoutSessionExpiredError:
            messages.warning(
                request,
                str(_("Your session has expired. Please start checkout again.")),
            )
            return redirect("shopping:cart")
        else:
            return redirect("orders:confirmation", number=order.number)

    context: dict[str, object] = {
        "checkout_session": session,
        "items": items,
        "error": error,
        **build_step_context(session),
    }
    return render(request, "checkout/review.html", context)
