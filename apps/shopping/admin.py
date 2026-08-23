from typing import TYPE_CHECKING
from typing import Any
from typing import cast

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Cart
from .models import CartItem
from .models import Collection
from .models import CollectionItem
from .models import Wishlist
from .models import WishlistItem

if TYPE_CHECKING:
    from decimal import Decimal

    from django.http import HttpRequest


class CartItemInline(admin.TabularInline[CartItem, Cart]):
    model = CartItem
    extra = 0
    readonly_fields = (
        "variant",
        "quantity",
        "unit_price_at_add",
        "line_total_display",
        "created",
    )
    fields = readonly_fields
    can_delete = False

    @admin.display(description=_("Line Total"))
    def line_total_display(self, obj: CartItem) -> Decimal | None:
        return obj.line_total

    def has_add_permission(self, request: HttpRequest, obj: Cart | None = None) -> bool:
        return False


class WishlistItemInline(admin.TabularInline[WishlistItem, Wishlist]):
    model = WishlistItem
    extra = 0
    readonly_fields = ("variant", "created")
    fields = readonly_fields
    can_delete = True


class CollectionItemInline(admin.TabularInline[CollectionItem, Collection]):
    model = CollectionItem
    extra = 0
    readonly_fields = ("variant", "created")
    fields = readonly_fields


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin[Cart]):
    list_display = ["id", "customer", "cart_type", "currency", "item_count", "created"]
    list_filter = ["cart_type", "currency"]
    search_fields = ["customer__user__email", "customer__first_name", "session_key"]
    readonly_fields = ["created", "modified"]
    list_select_related = ["customer", "currency"]
    inlines = [CartItemInline]
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "customer",
                    "session_key",
                    "cart_type",
                    "currency",
                    "coupon_code",
                )
            },
        ),
        (
            _("Timestamps"),
            {"fields": ("created", "modified"), "classes": ("collapse",)},
        ),
    )

    @admin.display(description=_("Items"))
    def item_count(self, obj: Cart) -> int:
        return int(cast("Any", obj).items.count())


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin[Wishlist]):
    list_display = ["customer", "item_count", "created"]
    search_fields = ["customer__user__email", "customer__first_name"]
    readonly_fields = ["created", "modified"]
    list_select_related = ["customer"]
    inlines = [WishlistItemInline]

    @admin.display(description=_("Items"))
    def item_count(self, obj: Wishlist) -> int:
        return int(cast("Any", obj).items.count())


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin[Collection]):
    list_display = ["name", "customer", "is_public", "item_count", "created"]
    list_filter = ["is_public"]
    search_fields = ["name", "customer__user__email", "customer__first_name"]
    prepopulated_fields = {"slug": ["name"]}
    readonly_fields = ["created", "modified"]
    list_select_related = ["customer"]
    inlines = [CollectionItemInline]

    @admin.display(description=_("Items"))
    def item_count(self, obj: Collection) -> int:
        return int(cast("Any", obj).items.count())
