"""
Django Unfold admin theme configuration.
"""

# ruff: noqa: PLC0415
from typing import TYPE_CHECKING

from django.templatetags.static import static
from django.urls import reverse
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    from typing import Any

    from django.http.request import HttpRequest

# Apps
# `unfold.apps.BasicAppConfig` must load before `django.contrib.admin` when
# we override the default admin site via `AdminConfig.default_site`. The
# optional `unfold.contrib.*` packages below add extra filter widgets /
# form fields / inline styling that admin.py files in this project use
# (numeric + dropdown filters, tabular/stacked inlines).
UNFOLD_APPS: list[str] = [
    "unfold.apps.BasicAppConfig",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "unfold.contrib.inlines",
]


def environment_callback(request: HttpRequest) -> list[str]:
    """Label shown top-right in the admin header."""
    from django.conf import settings

    if settings.DEBUG:
        return [str(_("Development")), "warning"]
    return [str(_("Production")), "danger"]


def badge_reviews_pending(request: HttpRequest) -> int:
    """Sidebar badge: count of unpublished reviews awaiting moderation."""
    from apps.reviews.models import ProductReview

    return ProductReview.objects.filter(is_published=False).count()


def dashboard_callback(request: HttpRequest, context: dict[str, Any]) -> dict[str, Any]:
    """Add custom stats to the admin dashboard."""
    from apps.catalogue.models import Product
    from apps.customers.models import CustomerProfile
    from apps.orders.models import Order
    from apps.reviews.models import ProductReview

    context.update(
        {
            "total_products": Product.objects.count(),
            "total_orders": Order.objects.count(),
            "total_customers": CustomerProfile.objects.count(),
            "pending_reviews": ProductReview.objects.filter(is_published=False).count(),
        }
    )
    return context


def tabs_callback(request: HttpRequest) -> list[dict[str, Any]]:
    """Build product tabs from the current admin request."""
    resolver_match = getattr(request, "resolver_match", None)
    if resolver_match is None:
        return []

    object_id = resolver_match.kwargs.get("object_id")
    if object_id is None:
        return []

    change_url = reverse(
        resolver_match.view_name,
        kwargs={"object_id": object_id},
    )

    return [
        {
            "models": ["catalogue.product", "catalogue.productvariant"],
            "items": [
                {
                    "title": _("General"),
                    "link": change_url,
                },
                {
                    "title": _("Attributes"),
                    "link": f"{change_url}#attributes",
                },
                {
                    "title": _("Variants"),
                    "link": f"{change_url}#variants",
                },
                {
                    "title": _("Images"),
                    "link": f"{change_url}#images",
                },
                {
                    "title": _("SEO"),
                    "link": f"{change_url}#seo",
                },
            ],
        },
    ]


UNFOLD = {
    "SITE_TITLE": "Digits",
    "SITE_HEADER": "Digits",
    "SITE_SUBHEADER": _("Administration"),
    "SITE_URL": "/",
    "SITE_SYMBOL": "Digits Internal Portal",
    "SITE_LOGO": {
        "light": lambda request: static("images/logo.svg"),
        "dark": lambda request: static("images/logo.svg"),
    },
    "SITE_ICON": {
        "light": lambda request: static("images/favicon.svg"),
        "dark": lambda request: static("images/favicon.svg"),
    },
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "SHOW_BACK_BUTTON": False,
    "ENVIRONMENT": "config.settings.apps.unfold.environment_callback",
    "BORDER_RADIUS": "6px",
    "FONTS": {
        "sans": {
            "regular": {
                "href": "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap",
                "family": "Inter",
            },
            "bold": {
                "href": "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap",
                "family": "Inter",
            },
        },
        "mono": {
            "regular": {
                "href": "https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap",
                "family": "JetBrains Mono",
            },
        },
    },
    "SIDEBAR_WIDTH": 280,
    "COLORS": {
        "primary": {
            "50": "oklch(97.7% .014 308.299)",
            "100": "oklch(94.6% .033 307.174)",
            "200": "oklch(90.2% .063 306.703)",
            "300": "oklch(82.7% .119 306.383)",
            "400": "oklch(71.4% .203 305.504)",
            "500": "oklch(62.7% .265 303.9)",
            "600": "oklch(55.8% .288 302.321)",
            "700": "oklch(49.6% .265 301.924)",
            "800": "oklch(43.8% .218 303.724)",
            "900": "oklch(38.1% .176 304.987)",
            "950": "oklch(29.1% .149 302.717)",
        },
        "base": {
            "50": "oklch(98.5% 0 0)",
            "100": "oklch(97% 0 0)",
            "200": "oklch(92.2% 0 0)",
            "300": "oklch(87.5% 0 0)",
            "400": "oklch(71.8% 0 0)",
            "500": "oklch(55.6% 0 0)",
            "600": "oklch(44.4% 0 0)",
            "700": "oklch(37.5% 0 0)",
            "800": "oklch(27.8% 0 0)",
            "900": "oklch(21.5% 0 0)",
            "950": "oklch(13.8% 0 0)",
        },
        "secondary": {
            "50": "oklch(97.1% .014 254.604)",
            "100": "oklch(92.8% .033 255.508)",
            "200": "oklch(86.4% .063 255.878)",
            "300": "oklch(77.1% .119 256.888)",
            "400": "oklch(66.7% .203 256.755)",
            "500": "oklch(55.8% .265 255.811)",
            "600": "oklch(49.6% .288 254.341)",
            "700": "oklch(43.8% .265 253.362)",
            "800": "oklch(38.1% .218 252.962)",
            "900": "oklch(32.8% .176 252.714)",
            "950": "oklch(25.1% .149 252.475)",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": True,
        "navigation": [
            {
                "title": _("Overview"),
                "separator": False,
                "items": [
                    {
                        "title": _("Dashboard"),
                        "icon": "dashboard",
                        "link": reverse_lazy("admin:index"),
                    },
                ],
            },
            {
                "title": _("Catalogue"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Products"),
                        "icon": "category",
                        "link": reverse_lazy(
                            "admin:app_list", kwargs={"app_label": "catalogue"}
                        ),
                    },
                    {
                        "title": _("Reviews"),
                        "icon": "reviews",
                        "link": reverse_lazy("admin:reviews_productreview_changelist"),
                        "badge": "config.settings.apps.unfold.badge_reviews_pending",
                    },
                ],
            },
            {
                "title": _("Sales"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Carts & wishlists"),
                        "icon": "shopping_cart",
                        "link": reverse_lazy("admin:shopping_cart_changelist"),
                    },
                    {
                        "title": _("Checkout sessions"),
                        "icon": "point_of_sale",
                        "link": reverse_lazy(
                            "admin:checkout_checkoutsession_changelist"
                        ),
                    },
                    {
                        "title": _("Orders"),
                        "icon": "receipt_long",
                        "link": reverse_lazy("admin:orders_order_changelist"),
                    },
                ],
            },
            {
                "title": _("Fulfilment & shipping"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Fulfilments"),
                        "icon": "local_shipping",
                        "link": reverse_lazy("admin:delivery_fulfilment_changelist"),
                    },
                    {
                        "title": _("Shipments"),
                        "icon": "local_shipping",
                        "link": reverse_lazy("admin:shipping_shipment_changelist"),
                    },
                    {
                        "title": _("Shipping methods"),
                        "icon": "conveyor_belt",
                        "link": reverse_lazy(
                            "admin:shipping_shippingmethod_changelist"
                        ),
                    },
                    {
                        "title": _("Carrier accounts"),
                        "icon": "local_shipping",
                        "link": reverse_lazy(
                            "admin:shipping_carrieraccount_changelist"
                        ),
                    },
                    {
                        "title": _("Warehouses"),
                        "icon": "warehouse",
                        "link": reverse_lazy("admin:inventory_warehouse_changelist"),
                    },
                    {
                        "title": _("Stock"),
                        "icon": "inventory_2",
                        "link": reverse_lazy("admin:inventory_stock_changelist"),
                    },
                    {
                        "title": _("Stock movements"),
                        "icon": "sync_alt",
                        "link": reverse_lazy(
                            "admin:inventory_stockmovement_changelist"
                        ),
                    },
                ],
            },
            {
                "title": _("Payments & pricing"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Payments"),
                        "icon": "payments",
                        "link": reverse_lazy("admin:payments_payment_changelist"),
                    },
                    {
                        "title": _("Refunds"),
                        "icon": "currency_exchange",
                        "link": reverse_lazy("admin:payments_refund_changelist"),
                    },
                    {
                        "title": _("Payment methods"),
                        "icon": "credit_card",
                        "link": reverse_lazy("admin:payments_paymentmethod_changelist"),
                    },
                    {
                        "title": _("Currencies"),
                        "icon": "currency_rupee",
                        "link": reverse_lazy("admin:pricing_currency_changelist"),
                    },
                    {
                        "title": _("Tax rates"),
                        "icon": "percent",
                        "link": reverse_lazy("admin:pricing_taxrate_changelist"),
                    },
                    {
                        "title": _("Pricing"),
                        "icon": "sell",
                        "link": reverse_lazy("admin:pricing_pricing_changelist"),
                    },
                ],
            },
            {
                "title": _("Marketing"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Campaigns"),
                        "icon": "campaign",
                        "link": reverse_lazy("admin:promotions_campaign_changelist"),
                    },
                    {
                        "title": _("Discounts"),
                        "icon": "percent_discount",
                        "link": reverse_lazy("admin:promotions_discount_changelist"),
                    },
                    {
                        "title": _("Coupons"),
                        "icon": "confirmation_number",
                        "link": reverse_lazy("admin:promotions_coupon_changelist"),
                    },
                ],
            },
            {
                "title": _("People"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("User accounts"),
                        "icon": "manage_accounts",
                        "link": reverse_lazy("admin:accounts_useraccount_changelist"),
                    },
                    {
                        "title": _("Customers"),
                        "icon": "group",
                        "link": reverse_lazy(
                            "admin:customers_customerprofile_changelist"
                        ),
                    },
                    {
                        "title": _("Staff"),
                        "icon": "badge",
                        "link": reverse_lazy("admin:staff_staffprofile_changelist"),
                        "permission": lambda request: request.user.is_superuser,
                    },
                    {
                        "title": _("Departments"),
                        "icon": "corporate_fare",
                        "link": reverse_lazy("admin:staff_staffdepartment_changelist"),
                        "permission": lambda request: request.user.is_superuser,
                    },
                ],
            },
            {
                "title": _("System"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Groups"),
                        "icon": "shield",
                        "link": reverse_lazy("admin:auth_group_changelist"),
                        "permission": lambda request: request.user.is_superuser,
                    },
                ],
            },
        ],
    },
    "TABS": "config.settings.apps.unfold.tabs_callback",
    "THEME": "light",
    "LANGUAGES": {
        "navigation": [
            ("en", _("English")),
        ],
    },
    "STYLES": [
        lambda request: static("css/admin-custom.css"),
    ],
    "SCRIPTS": [
        lambda request: static("js/admin-custom.js"),
    ],
    "DASHBOARD_CALLBACK": "config.settings.apps.unfold.dashboard_callback",
}
