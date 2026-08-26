from __future__ import annotations

from django.core.paginator import Paginator
from django.http import Http404
from django.http import HttpRequest
from django.http import HttpResponse
from django.shortcuts import render

from apps.orders.enums import OrderStatusEnum
from apps.orders.models import OrderItem
from apps.orders.models import ReturnRequest
from apps.orders.service.storefront import OrderStorefrontService
from core.decorators import require_customer
from core.exceptions import ReturnError

_MAX_REASON_LEN = 500
_MAX_NOTE_LEN = 2000


@require_customer
def order_history(request: HttpRequest) -> HttpResponse:
    """Display paginated order history for the authenticated customer."""
    customer = request.user.customer_profile  # type: ignore[union-attr]
    page_number = request.GET.get("page", 1)
    svc = OrderStorefrontService()
    qs = svc.get_orders_for_customer(customer, page=int(page_number))
    paginator = Paginator(qs, OrderStorefrontService.PAGE_SIZE)
    page_obj = paginator.get_page(page_number)
    return render(request, "orders/history.html", {"page_obj": page_obj})


@require_customer
def order_confirmation(request: HttpRequest, number: str) -> HttpResponse:
    """Display the order confirmation page."""
    customer = request.user.customer_profile  # type: ignore[union-attr]
    order = OrderStorefrontService().get_order_detail(customer, number)
    if order is None:
        raise Http404
    return render(request, "orders/confirmation.html", {"order": order})


@require_customer
def order_detail(request: HttpRequest, number: str) -> HttpResponse:
    """Display order detail with status history."""
    customer = request.user.customer_profile  # type: ignore[union-attr]
    order = OrderStorefrontService().get_order_detail(customer, number)
    if order is None:
        raise Http404
    status_history = order.status_history.order_by("changed_at")
    can_return = order.status == OrderStatusEnum.DELIVERED and not (
        ReturnRequest.objects.filter(order=order)
        .exclude(status__in=ReturnRequest.TERMINAL_STATUSES)
        .exists()
    )
    breadcrumb_items = [
        {"label": "Home", "url": "/"},
        {"label": "Orders", "url": "/orders/"},
        {"label": order.number, "url": ""},
    ]
    return render(
        request,
        "orders/detail.html",
        {
            "order": order,
            "status_history": status_history,
            "can_return": can_return,
            "breadcrumb_items": breadcrumb_items,
        },
    )


@require_customer
def return_request_create(request: HttpRequest, number: str) -> HttpResponse:
    """Create a return request for an order."""
    customer = request.user.customer_profile  # type: ignore[union-attr]
    svc = OrderStorefrontService()
    order = svc.get_order_detail(customer, number)
    if order is None:
        raise Http404

    if request.method == "POST":
        reason = request.POST.get("reason", "").strip()
        note = request.POST.get("note", "").strip()
        item_ids = request.POST.getlist("item_ids")
        errors: dict[str, str] = {}

        if not reason:
            errors["reason"] = "Reason is required."
        elif len(reason) > _MAX_REASON_LEN:
            errors["reason"] = f"Reason must be at most {_MAX_REASON_LEN} characters."
        if len(note) > _MAX_NOTE_LEN:
            errors["note"] = f"Note must be at most {_MAX_NOTE_LEN} characters."
        if not item_ids:
            errors["item_ids"] = "Please select at least one item to return."

        if not errors:
            items = list(OrderItem.objects.filter(order=order, pk__in=item_ids))
            try:
                rr = svc.create_return_request(
                    customer=customer,
                    order=order,
                    items=items,
                    reason=reason,
                    note=note,
                )
                return render(
                    request,
                    "orders/return_form.html",
                    {
                        "order": order,
                        "return_request": rr,
                        "success": True,
                    },
                )
            except (ValueError, ReturnError) as exc:
                errors["non_field"] = str(exc)

        return render(
            request,
            "orders/return_form.html",
            {
                "order": order,
                "errors": errors,
                "submitted_reason": reason,
                "submitted_note": note,
                "submitted_item_ids": item_ids,
            },
        )

    return render(request, "orders/return_form.html", {"order": order})
