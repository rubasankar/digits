from typing import TYPE_CHECKING

from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from model_utils.models import TimeStampedModel
from model_utils.models import UUIDModel

from apps.shopping.enums import CartType
from core.models import BaseModel

if TYPE_CHECKING:
    from decimal import Decimal


class Cart(UUIDModel, TimeStampedModel):
    """
    Represents a shopping cart - either belonging to a logged-in customer
    or to an anonymous guest (identified by session_key).

    Cart merge
    ----------
    When a guest logs in, the guest cart must be merged into the customer's
    active cart.  This is handled entirely in the service layer
    (CartMergeService) - never in the model - so the merge logic can:
      - add quantities for matching variants (respecting stock limits)
      - carry over the coupon code if the customer cart has none
      - archive the guest cart (cart_type -> MERGED) after the merge

    The ``merged_into`` field records the lineage: after a merge the guest
    cart points to the surviving customer cart.  This gives a clean audit
    trail without duplicating cart items.

    Merge algorithm (CartMergeService.merge):
      1. Load the guest cart and the customer's ACTIVE cart.
         If the customer has no ACTIVE cart, simply reassign the guest cart
         to the customer (set cart.customer, clear cart.session_key).
      2. For each CartItem in the guest cart:
           - If an identical variant already exists in the customer cart,
             add quantities (capped at Stock.maximum_order_qty).
           - Otherwise move the CartItem to the customer cart.
      3. Copy coupon_code from guest cart if customer cart has none.
      4. Set guest_cart.cart_type = CartType.MERGED and
         guest_cart.merged_into = customer_cart, then save.
      5. Run everything in a single atomic transaction.
    """

    customer = models.ForeignKey(
        "customers.CustomerProfile",
        verbose_name=_("Customer"),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="carts",
        help_text=_("Null for guest carts. Identified by session_key instead."),
    )
    session_key = models.CharField(
        _("Session Key"),
        max_length=40,
        blank=True,
        db_index=True,
        help_text=_("Django session key for guest cart identification."),
    )
    cart_type = models.CharField(
        _("Cart Type"),
        max_length=10,
        choices=CartType.choices,
        default=CartType.ACTIVE,
    )
    currency = models.ForeignKey(
        "pricing.Currency",
        verbose_name=_("Currency"),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="carts",
        help_text=_("Currency used to display prices in this cart."),
    )
    coupon_code = models.CharField(
        _("Coupon Code"),
        max_length=50,
        blank=True,
        help_text=_("Coupon applied to this cart. Validated at checkout."),
    )
    merged_into = models.ForeignKey(
        "self",
        verbose_name=_("Merged Into"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="merged_carts",
        help_text=_(
            "Set by CartMergeService when this guest cart is merged into a "
            "customer cart. The referenced cart is the surviving cart. "
            "Only populated when cart_type = MERGED."
        ),
    )

    class Meta:
        verbose_name = _("Cart")
        verbose_name_plural = _("Carts")
        ordering = ["-created"]
        constraints = [
            models.UniqueConstraint(
                fields=["customer", "cart_type"],
                condition=models.Q(customer__isnull=False),
                name="unique_cart_type_per_customer",
            ),
            models.UniqueConstraint(
                fields=["session_key", "cart_type"],
                condition=models.Q(customer__isnull=True) & ~models.Q(session_key=""),
                name="unique_cart_type_per_session",
            ),
        ]

    def __str__(self) -> str:
        owner = str(self.customer) if self.customer else f"guest:{self.session_key}"
        return f"Cart({self.cart_type}) -- {owner}"

    def __repr__(self) -> str:
        return (
            f"<Cart id={self.id} type={self.cart_type} "
            f"customer={self.customer} session={self.session_key!r}>"
        )


class CartItem(UUIDModel, TimeStampedModel):
    cart = models.ForeignKey(
        Cart,
        verbose_name=_("Cart"),
        on_delete=models.CASCADE,
        related_name="items",
    )
    variant = models.ForeignKey(
        "catalogue.ProductVariant",
        verbose_name=_("Product Variant"),
        on_delete=models.CASCADE,
        related_name="cart_items",
    )
    quantity = models.PositiveSmallIntegerField(
        _("Quantity"),
        default=1,
        validators=[MinValueValidator(1)],
    )
    unit_price_at_add = models.DecimalField(
        _("Unit Price at Add"),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_(
            "Base price per unit when this item was added. "
            "Used to detect price changes before checkout."
        ),
    )

    class Meta:
        verbose_name = _("Cart Item")
        verbose_name_plural = _("Cart Items")
        constraints = [
            models.UniqueConstraint(
                fields=["cart", "variant"],
                name="unique_variant_per_cart",
            )
        ]

    @property
    def line_total(self) -> Decimal | None:
        """Indicative total = unit_price_at_add * quantity. Recalculated at checkout."""
        if self.unit_price_at_add is not None:
            return self.unit_price_at_add * self.quantity
        return None

    def __str__(self) -> str:
        return f"{self.variant} x {self.quantity}"

    def __repr__(self) -> str:
        return (
            f"<CartItem id={self.id} cart={self.cart} "
            f"variant={self.variant} qty={self.quantity}>"
        )


class Wishlist(UUIDModel, TimeStampedModel):
    customer = models.OneToOneField(
        "customers.CustomerProfile",
        verbose_name=_("Customer"),
        on_delete=models.CASCADE,
        related_name="wishlist",
    )

    class Meta:
        verbose_name = _("Wishlist")
        verbose_name_plural = _("Wishlists")

    def __str__(self) -> str:
        return f"Wishlist -- {self.customer}"

    def __repr__(self) -> str:
        return f"<Wishlist id={self.id} customer={self.customer}>"


class WishlistItem(UUIDModel, TimeStampedModel):
    wishlist = models.ForeignKey(
        Wishlist,
        verbose_name=_("Wishlist"),
        on_delete=models.CASCADE,
        related_name="items",
    )
    variant = models.ForeignKey(
        "catalogue.ProductVariant",
        verbose_name=_("Product Variant"),
        on_delete=models.CASCADE,
        related_name="wishlist_items",
    )

    class Meta:
        verbose_name = _("Wishlist Item")
        verbose_name_plural = _("Wishlist Items")
        constraints = [
            models.UniqueConstraint(
                fields=["wishlist", "variant"],
                name="unique_variant_per_wishlist",
            )
        ]

    def __str__(self) -> str:
        return f"{self.variant} -- wishlist {self.wishlist}"

    def __repr__(self) -> str:
        return f"<WishlistItem id={self.id} variant={self.variant}>"


class Collection(BaseModel):
    customer = models.ForeignKey(
        "customers.CustomerProfile",
        verbose_name=_("Customer"),
        on_delete=models.CASCADE,
        related_name="collections",
    )
    is_public = models.BooleanField(
        _("Public"),
        default=False,
        help_text=_("Allow anyone with the link to view this collection."),
    )

    class Meta:
        verbose_name = _("Collection")
        verbose_name_plural = _("Collections")

    def __repr__(self) -> str:
        return f"<Collection id={self.id} name={self.name!r} customer={self.customer}>"


class CollectionItem(UUIDModel, TimeStampedModel):
    collection = models.ForeignKey(
        Collection,
        verbose_name=_("Collection"),
        on_delete=models.CASCADE,
        related_name="items",
    )
    variant = models.ForeignKey(
        "catalogue.ProductVariant",
        verbose_name=_("Product Variant"),
        on_delete=models.CASCADE,
        related_name="collection_items",
    )

    class Meta:
        verbose_name = _("Collection Item")
        verbose_name_plural = _("Collection Items")
        constraints = [
            models.UniqueConstraint(
                fields=["collection", "variant"],
                name="unique_variant_per_collection",
            )
        ]

    def __str__(self) -> str:
        return f"{self.variant} in {self.collection}"

    def __repr__(self) -> str:
        return (
            f"<CollectionItem id={self.id} collection={self.collection} "
            f"variant={self.variant}>"
        )
