from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render

from apps.catalogue.models.product import ProductVariant
from apps.shopping.models import CartItem
from apps.shopping.service.cart import CartService

if TYPE_CHECKING:
    from uuid import UUID

    from django.http import HttpRequest
    from django.http import HttpResponse


def cart_detail(request: HttpRequest) -> HttpResponse:
    """Display the cart with all items and order summary."""
    service = CartService()
    cart = service.get_or_create_cart(request)
    items = (
        CartItem.objects.filter(cart=cart)
        .select_related("variant__product")
        .prefetch_related("variant__images", "variant__prices")
    )
    subtotal: Decimal = sum(
        (item.line_total for item in items if item.line_total is not None),
        Decimal("0.00"),
    )
    breadcrumb_items = [
        {"label": "Home", "url": "/"},
        {"label": "Cart", "url": ""},
    ]
    return render(
        request,
        "shopping/cart.html",
        {
            "cart": cart,
            "items": items,
            "subtotal": subtotal,
            "breadcrumb_items": breadcrumb_items,
        },
    )


def cart_add(request: HttpRequest) -> HttpResponse:
    """Add a variant to the cart. Returns HTMX partial or redirect."""
    if request.method != "POST":
        return redirect("shopping:cart")

    variant_id_raw = request.POST.get("variant_id", "")
    quantity_raw = request.POST.get("quantity", "1")

    try:
        variant = get_object_or_404(ProductVariant, pk=variant_id_raw, is_active=True)
        quantity = int(quantity_raw)
    except ValueError, TypeError:
        messages.error(request, "Invalid quantity.")
        return redirect("shopping:cart")

    service = CartService()
    cart = service.get_or_create_cart(request)

    try:
        service.add_item(cart, variant, quantity)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("shopping:cart")

    if request.headers.get("HX-Request"):
        cart_item_count = service.get_cart_item_count(request)
        return render(
            request,
            "cotton/components/badge/cart.html",
            {"cart_item_count": cart_item_count},
        )
    return redirect("shopping:cart")


def cart_update(request: HttpRequest, item_id: UUID) -> HttpResponse:
    """Update a cart item quantity."""
    if request.method != "POST":
        return redirect("shopping:cart")

    quantity_raw = request.POST.get("quantity", "")
    try:
        quantity = int(quantity_raw)
    except ValueError, TypeError:
        messages.error(request, "Invalid quantity.")
        return redirect("shopping:cart")

    service = CartService()
    cart = service.get_or_create_cart(request)

    try:
        service.update_item(cart, item_id, quantity)
    except (ValueError, CartItem.DoesNotExist) as exc:
        messages.error(request, str(exc))

    return redirect("shopping:cart")


def cart_remove(request: HttpRequest, item_id: UUID) -> HttpResponse:
    """Remove an item from the cart."""
    if request.method != "POST":
        return redirect("shopping:cart")

    service = CartService()
    cart = service.get_or_create_cart(request)
    service.remove_item(cart, item_id)
    return redirect("shopping:cart")


def cart_apply_coupon(request: HttpRequest) -> HttpResponse:
    """Apply a coupon code to the cart."""
    if request.method != "POST":
        return redirect("shopping:cart")

    code = request.POST.get("coupon_code", "").strip()
    service = CartService()
    cart = service.get_or_create_cart(request)

    try:
        service.apply_coupon(cart, code)
        messages.success(request, "Coupon applied.")
    except ValueError as exc:
        messages.error(request, str(exc))

    return redirect("shopping:cart")
