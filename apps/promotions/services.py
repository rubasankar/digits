from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.catalogue.models.category import ProductCategory
from core.exceptions import CouponAlreadyUsedByCustomerError
from core.exceptions import CouponExpiredError
from core.exceptions import CouponInactiveError
from core.exceptions import CouponNotFoundError
from core.exceptions import CouponUsageLimitReachedError

from .enums import ApplyTypeEnum
from .enums import DiscountTypeEnum
from .models import Coupon
from .models import CouponRedemption
from .models import Discount

if TYPE_CHECKING:
    from apps.customers.models import CustomerProfile
    from apps.orders.models import Order
    from apps.shopping.models import CartItem


# CouponService


class CouponService:
    @classmethod
    def _check_campaign_dates(cls, coupon: Coupon) -> None:
        """Raise if the coupon or its campaign is outside its active window."""
        now = timezone.now()
        campaign = coupon.discount.campaign
        if now < campaign.start_date or now > campaign.end_date:
            raise CouponExpiredError(
                str(_("This coupon's campaign is not currently running."))
            )
        if now < coupon.valid_from:
            msg = f"Coupon is not yet valid (starts {coupon.valid_from.date()})."
            raise CouponExpiredError(msg)
        if now > coupon.valid_to:
            msg_0 = "This coupon has expired."
            raise CouponExpiredError(msg_0)

    @classmethod
    def _check_usage_limits(cls, coupon: Coupon, customer: CustomerProfile) -> None:
        """Raise if total or per-user redemption limits have been reached."""
        if coupon.usage_limit_total is not None:
            total_used = CouponRedemption.objects.filter(coupon=coupon).count()
            if total_used >= coupon.usage_limit_total:
                raise CouponUsageLimitReachedError
        user_used = CouponRedemption.objects.filter(
            coupon=coupon, customer=customer
        ).count()
        if user_used >= coupon.usage_limit_per_user:
            raise CouponAlreadyUsedByCustomerError

    @classmethod
    def validate(
        cls,
        code: str,
        *,
        customer: CustomerProfile,
        cart_sub_total: Decimal,
    ) -> Coupon:
        try:
            coupon = Coupon.objects.select_related("discount__campaign").get(
                code__iexact=code.strip()
            )
        except Coupon.DoesNotExist as err:
            raise CouponNotFoundError from err

        if not coupon.is_active:
            raise CouponInactiveError

        campaign = coupon.discount.campaign
        if not campaign.is_active:
            raise CouponInactiveError

        cls._check_campaign_dates(coupon)
        cls._check_usage_limits(coupon, customer)

        # Minimum cart value
        discount = coupon.discount
        if discount.minimum_cart_value and cart_sub_total < discount.minimum_cart_value:
            raise CouponInactiveError(
                _("Minimum cart value of %(min)s required for this coupon.")
                % {"min": discount.minimum_cart_value}
            )

        return coupon

    @classmethod
    @transaction.atomic
    def redeem(
        cls,
        coupon: Coupon,
        *,
        customer: CustomerProfile,
        order: Order,
    ) -> CouponRedemption:
        # validate() checks the usage limits without locking, so two
        # concurrent redemptions could both pass it before either commits.
        # Lock the coupon row here to serialise concurrent redeem() calls for
        # the same coupon, then re-check the limits under that lock -- this
        # is the authoritative check, right before the redemption commits.
        locked_coupon = Coupon.objects.select_for_update().get(pk=coupon.pk)

        if locked_coupon.usage_limit_total is not None:
            total_used = CouponRedemption.objects.filter(coupon=locked_coupon).count()
            if total_used >= locked_coupon.usage_limit_total:
                raise CouponUsageLimitReachedError

        user_used = CouponRedemption.objects.filter(
            coupon=locked_coupon, customer=customer
        ).count()
        if user_used >= locked_coupon.usage_limit_per_user:
            raise CouponAlreadyUsedByCustomerError

        redemption = CouponRedemption(
            coupon=locked_coupon,
            customer=customer,
            order=order,
        )
        redemption.save()

        # Increment times_used atomically (via F() expression) to avoid lost updates.
        Discount.objects.filter(pk=locked_coupon.discount_id).update(
            times_used=F("times_used") + 1
        )

        return redemption


# DiscountService


class DiscountService:
    @classmethod
    def calculate(
        cls,
        discount: Discount,
        *,
        cart_sub_total: Decimal,
        shipping_cost: Decimal = Decimal("0.00"),
        cart_items: list[CartItem] | None = None,
    ) -> Decimal:
        dt = discount.discount_type
        applies_to = discount.applies_to

        if dt == DiscountTypeEnum.FREE_SHIPPING:
            return shipping_cost.quantize(Decimal("0.01"))

        if applies_to == ApplyTypeEnum.CART:
            base_amount = cart_sub_total
        elif applies_to in (
            ApplyTypeEnum.PRODUCT,
            ApplyTypeEnum.CATEGORY,
            ApplyTypeEnum.VARIANT,
        ):
            base_amount = cls._targeted_base(discount, cart_items or [])
        else:
            base_amount = cart_sub_total

        if dt == DiscountTypeEnum.PERCENTAGE:
            raw = base_amount * (discount.value or Decimal("0")) / Decimal("100")
        elif dt == DiscountTypeEnum.FIXED:
            raw = discount.value or Decimal("0")
        else:
            raw = Decimal("0")

        # Apply the maximum discount cap if set.
        if discount.max_discount_amount is not None:
            raw = min(raw, discount.max_discount_amount)

        # Discount cannot exceed the base it was applied to.
        raw = min(raw, base_amount)

        return max(raw, Decimal("0")).quantize(Decimal("0.01"))

    @classmethod
    def _targeted_base(
        cls,
        discount: Discount,
        cart_items: list[CartItem],
    ) -> Decimal:
        """
        Sum the line totals of cart items that match the discount target.
        """
        total = Decimal("0.00")

        for item in cart_items:
            if cls._item_matches(discount, item):
                line = item.line_total
                if line is not None:
                    total += line

        return total

    @classmethod
    def _item_matches(cls, discount: Discount, item: CartItem) -> bool:
        """Return True if the cart item is covered by this discount's target."""
        applies_to = discount.applies_to
        variant = item.variant

        if applies_to == ApplyTypeEnum.VARIANT:
            return bool(discount.target_variant_id == variant.pk)

        if applies_to == ApplyTypeEnum.PRODUCT:
            return bool(discount.target_product_id == variant.product_id)

        if applies_to == ApplyTypeEnum.CATEGORY:
            if discount.target_category_id is None:
                return False
            # Check the variant's product category and its ancestors.
            product_category = variant.product.category
            return cls._is_in_category(product_category, discount.target_category_id)

        return False

    @classmethod
    def _is_in_category(
        cls,
        category: ProductCategory,
        target_category_id: object,
    ) -> bool:
        """
        Return True if *category* is *target_category* or a descendant of it.

        Uses the materialised path from treebeard to avoid N+1 queries.
        """
        # category.path starts with the root's path; target ancestor's path
        # is a prefix of category.path.

        try:
            target = ProductCategory.objects.get(pk=target_category_id)
        except ProductCategory.DoesNotExist:
            return False

        # The category is the target itself, or its path starts with target.path
        return bool(category.pk == target.pk or category.path.startswith(target.path))
