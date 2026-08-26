from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string

from apps.catalogue.models.category import ProductCategory
from apps.catalogue.models.product import Product
from apps.catalogue.service.storefront import CatalogueStorefrontService

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.http import HttpRequest

logger = logging.getLogger(__name__)


def home(request: HttpRequest) -> HttpResponse:
    """Render the storefront homepage with featured categories and products."""
    svc = CatalogueStorefrontService()
    featured_categories: QuerySet[ProductCategory]
    featured_products: QuerySet[Product]

    try:
        featured_categories = svc.get_featured_categories(limit=8)
    except Exception:
        logger.exception("Failed to load featured categories for homepage")
        featured_categories = ProductCategory.objects.none()

    try:
        featured_products = svc.get_featured_products(limit=12)
    except Exception:
        logger.exception("Failed to load featured products for homepage")
        featured_products = Product.objects.none()

    return render(
        request,
        "home.html",
        {
            "featured_categories": featured_categories,
            "featured_products": featured_products,
        },
    )


def handler_400(
    request: HttpRequest, exception: Exception | None = None
) -> HttpResponse:
    """Return a 400 Bad Request response."""
    return render(request, "400.html", status=400)


def handler_403(
    request: HttpRequest, exception: Exception | None = None
) -> HttpResponse:
    """Return a 403 Forbidden response."""
    return render(request, "403.html", status=403)


def handler_404(
    request: HttpRequest, exception: Exception | None = None
) -> HttpResponse:
    """Return a 404 Not Found response."""
    return render(request, "404.html", status=404)


def handler_500(request: HttpRequest) -> HttpResponse:
    """Return a 500 response without context processors (safe during DB outages)."""
    html = render_to_string("500.html")
    return HttpResponse(html, status=500)
