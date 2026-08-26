from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from model_utils.models import TimeStampedModel
from model_utils.models import UUIDModel

from core.models import BaseModel

from .enums import ApplyTypeEnum
from .enums import DiscountTypeEnum

MAX_PERCENTAGE = 100


class Campaign(BaseModel):
    start_date = models.DateTimeField(_("Start Date"))
    end_date = models.DateTimeField(_("End Date"))
    is_active = models.BooleanField(
        _("Active"),
        default=False,
        help_text=_("Must also be within start/end date range to be live."),
    )

    class Meta:
        verbose_name = _("Campaign")
        verbose_name_plural = _("Campaigns")
        ordering = ["-start_date"]

    def clean(self) -> None:
        super().clean()
        if self.start_date and self.end_date and self.end_date <= self.start_date:
            raise ValidationError({"end_date": _("End date must be after start date.")})

    def __repr__(self) -> str:
        return f"<Campaign id={self.id} name={self.name!r} active={self.is_active}>"


class Discount(UUIDModel, TimeStampedModel):
    ApplyType = ApplyTypeEnum
    DiscountType = DiscountTypeEnum

    campaign = models.ForeignKey(
        Campaign,
        verbose_name=_("Campaign"),
        on_delete=models.CASCADE,
        related_name="discounts",
    )
    discount_type = models.CharField(
        _("Discount Type"),
        max_length=15,
        choices=DiscountType.choices,
        default=DiscountType.PERCENTAGE,
    )
    value = models.DecimalField(
        _("Discount Value"),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_(
            "Percentage (0-100) for PERCENTAGE type, or a fixed currency amount "
            "for FIXED type. Leave blank for FREE_SHIPPING."
        ),
    )
    applies_to = models.CharField(
        _("Applies To"),
        max_length=10,
        choices=ApplyType.choices,
        default=ApplyType.CART,
    )

    target_product = models.ForeignKey(
        "catalogue.Product",
        verbose_name=_("Target Product"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="discounts",
        help_text=_("Set when applies_to = PRODUCT."),
    )
    target_category = models.ForeignKey(
        "catalogue.ProductCategory",
        verbose_name=_("Target Category"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="discounts",
        help_text=_("Set when applies_to = CATEGORY."),
    )
    target_variant = models.ForeignKey(
        "catalogue.ProductVariant",
        verbose_name=_("Target Variant"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="discounts",
        help_text=_("Set when applies_to = VARIANT."),
    )

    minimum_cart_value = models.DecimalField(
        _("Minimum Cart Value"),
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text=_(
            "Cart sub-total must reach this before the discount applies. "
            "0 = no minimum."
        ),
    )
    max_discount_amount = models.DecimalField(
        _("Maximum Discount Amount"),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_(
            "Caps the discount value. Useful for percentage discounts. Null = no cap."
        ),
    )
    usage_limit_total = models.PositiveIntegerField(
        _("Total Usage Limit"),
        null=True,
        blank=True,
        help_text=_("Maximum total redemptions. Null = unlimited."),
    )
    times_used = models.PositiveIntegerField(
        _("Times Used"),
        default=0,
        help_text=_("Number of times this discount has been redeemed."),
    )
    slug = models.SlugField(
        _("Slug"),
        max_length=100,
        unique=True,
        db_index=True,
        help_text=_(
            "URL-safe unique identifier for this discount rule, "
            "e.g. 'back-to-school-cart-10pct'. Auto-generated from campaign and "
            "discount type if left blank."
        ),
    )

    class Meta:
        verbose_name = _("Discount")
        verbose_name_plural = _("Discounts")
        ordering = ["-created"]
        constraints = [
            # CART: all target FKs must be null.
            models.CheckConstraint(
                condition=(
                    Q(applies_to="CART")
                    & Q(target_product__isnull=True)
                    & Q(target_category__isnull=True)
                    & Q(target_variant__isnull=True)
                )
                | Q(applies_to="PRODUCT")
                | Q(applies_to="CATEGORY")
                | Q(applies_to="VARIANT"),
                name="discount_cart_has_no_target",
            ),
            # PRODUCT: exactly target_product set, others null.
            models.CheckConstraint(
                condition=(
                    Q(applies_to="PRODUCT")
                    & Q(target_product__isnull=False)
                    & Q(target_category__isnull=True)
                    & Q(target_variant__isnull=True)
                )
                | ~Q(applies_to="PRODUCT"),
                name="discount_product_target_exclusive",
            ),
            # CATEGORY: exactly target_category set, others null.
            models.CheckConstraint(
                condition=(
                    Q(applies_to="CATEGORY")
                    & Q(target_product__isnull=True)
                    & Q(target_category__isnull=False)
                    & Q(target_variant__isnull=True)
                )
                | ~Q(applies_to="CATEGORY"),
                name="discount_category_target_exclusive",
            ),
            # VARIANT: exactly target_variant set, others null.
            models.CheckConstraint(
                condition=(
                    Q(applies_to="VARIANT")
                    & Q(target_product__isnull=True)
                    & Q(target_category__isnull=True)
                    & Q(target_variant__isnull=False)
                )
                | ~Q(applies_to="VARIANT"),
                name="discount_variant_target_exclusive",
            ),
            # minimum_cart_value must be non-negative (0 = no minimum).
            models.CheckConstraint(
                condition=Q(minimum_cart_value__gte=0),
                name="discount_minimum_cart_value_non_negative",
            ),
            # max_discount_amount must be positive when set.
            models.CheckConstraint(
                condition=Q(max_discount_amount__isnull=True)
                | Q(max_discount_amount__gt=0),
                name="discount_max_discount_amount_positive",
            ),
            # FIXED discount value must be positive when set.
            models.CheckConstraint(
                condition=~Q(discount_type="FIXED")
                | Q(value__isnull=True)
                | Q(value__gt=0),
                name="discount_fixed_value_positive",
            ),
            # PERCENTAGE discount value must be in (0, 100] when set.
            models.CheckConstraint(
                condition=~Q(discount_type="PERCENTAGE")
                | Q(value__isnull=True)
                | (Q(value__gt=0) & Q(value__lte=100)),
                name="discount_percentage_value_range",
            ),
            # FREE_SHIPPING discount value must be null.
            models.CheckConstraint(
                condition=~Q(discount_type="FREE_SHIPPING") | Q(value__isnull=True),
                name="discount_free_shipping_value_null",
            ),
        ]

    def _validate_target_exclusivity(self) -> None:
        """Ensure exactly the right target FK is set for the applies_to value."""
        target_field_map: dict[str, str] = {
            self.ApplyType.PRODUCT: "target_product",
            self.ApplyType.CATEGORY: "target_category",
            self.ApplyType.VARIANT: "target_variant",
        }
        all_target_fields = list(target_field_map.values())

        if self.applies_to == self.ApplyType.CART:
            for field in all_target_fields:
                if getattr(self, f"{field}_id") is not None:
                    raise ValidationError(
                        {field: _("Target must be empty when applies_to is CART.")}
                    )
            return

        required_field = target_field_map.get(self.applies_to)
        if required_field is None:
            return

        if getattr(self, f"{required_field}_id") is None:
            raise ValidationError(
                {
                    required_field: _("Required when applies_to = %(applies_to)s.")
                    % {"applies_to": self.applies_to}
                }
            )
        for field in all_target_fields:
            if field != required_field and getattr(self, f"{field}_id") is not None:
                raise ValidationError(
                    {
                        field: _("Must be empty when applies_to = %(applies_to)s.")
                        % {"applies_to": self.applies_to}
                    }
                )

    def _validate_value_and_guards(self) -> None:
        """Validate discount value range and guard fields."""
        if (
            self.discount_type == self.DiscountType.PERCENTAGE
            and self.value is not None
            and not (0 < self.value <= MAX_PERCENTAGE)
        ):
            raise ValidationError(
                {"value": _("Percentage discount must be between 0 and 100.")}
            )

        if (
            self.discount_type == self.DiscountType.FIXED
            and self.value is not None
            and self.value <= 0
        ):
            raise ValidationError(
                {"value": _("Fixed discount amount must be greater than zero.")}
            )

        if (
            self.discount_type == self.DiscountType.FREE_SHIPPING
            and self.value is not None
        ):
            raise ValidationError(
                {"value": _("Value must be blank for FREE_SHIPPING discounts.")}
            )

        if self.minimum_cart_value is not None and self.minimum_cart_value < 0:
            raise ValidationError(
                {"minimum_cart_value": _("Minimum cart value cannot be negative.")}
            )

        if self.max_discount_amount is not None and self.max_discount_amount <= 0:
            raise ValidationError(
                {
                    "max_discount_amount": _(
                        "Maximum discount amount must be greater than zero."
                    )
                }
            )

    def clean(self) -> None:
        super().clean()
        self._validate_target_exclusivity()
        self._validate_value_and_guards()

    def save(self, *args: object, **kwargs: object) -> None:
        if not self.slug:
            campaign_slug = getattr(self.campaign, "slug", "") or ""
            self.slug = slugify(
                f"{campaign_slug}-{self.discount_type}-{self.applies_to}"
            )[:100]
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        try:
            discount_label = self.DiscountType(self.discount_type).label
        except ValueError:
            discount_label = self.discount_type
        return f"{self.campaign} -- {discount_label}"

    def __repr__(self) -> str:
        return (
            f"<Discount id={self.id} campaign={self.campaign} "
            f"type={self.discount_type} applies_to={self.applies_to}>"
        )


class Coupon(UUIDModel, TimeStampedModel):
    discount = models.ForeignKey(
        Discount,
        verbose_name=_("Discount"),
        on_delete=models.CASCADE,
        related_name="coupons",
    )
    code = models.CharField(
        _("Coupon Code"),
        max_length=50,
        unique=True,
        db_index=True,
        help_text=_(
            "Code customers enter at checkout."
            " Stored and compared case-insensitively in the service layer."
        ),
    )
    usage_limit_total = models.PositiveIntegerField(
        _("Total Usage Limit"),
        null=True,
        blank=True,
        help_text=_("Maximum total redemptions. Null = unlimited."),
    )
    usage_limit_per_user = models.PositiveSmallIntegerField(
        _("Per-User Usage Limit"),
        default=1,
        help_text=_("How many times a single user may use this code."),
    )
    valid_from = models.DateTimeField(_("Valid From"))
    valid_to = models.DateTimeField(_("Valid To"))
    is_active = models.BooleanField(_("Active"), default=True)

    class Meta:
        verbose_name = _("Coupon")
        verbose_name_plural = _("Coupons")
        ordering = ["-valid_from"]

    def clean(self) -> None:
        super().clean()
        if self.valid_from and self.valid_to and self.valid_to <= self.valid_from:
            raise ValidationError({"valid_to": _("Valid To must be after Valid From.")})
        self._validate_campaign_date_range()

    def _validate_campaign_date_range(self) -> None:
        """Validate Coupon validity window falls within Campaign date range."""
        if self.discount_id:
            campaign = self.discount.campaign
            if campaign:
                if (
                    self.valid_from
                    and campaign.start_date
                    and self.valid_from < campaign.start_date
                ):
                    raise ValidationError(
                        {
                            "valid_from": _(
                                "Coupon valid_from must be on or after "
                                "campaign start_date."
                            )
                        }
                    )
                if (
                    self.valid_to
                    and campaign.end_date
                    and self.valid_to > campaign.end_date
                ):
                    raise ValidationError(
                        {
                            "valid_to": _(
                                "Coupon valid_to must be on or before "
                                "campaign end_date."
                            )
                        }
                    )

    def __str__(self) -> str:
        return self.code

    def __repr__(self) -> str:
        return f"<Coupon id={self.id} code={self.code!r} active={self.is_active}>"


class CouponRedemption(models.Model):
    coupon = models.ForeignKey(
        Coupon,
        verbose_name=_("Coupon"),
        on_delete=models.PROTECT,
        related_name="redemptions",
    )
    customer = models.ForeignKey(
        "customers.CustomerProfile",
        verbose_name=_("Customer"),
        on_delete=models.PROTECT,
        related_name="coupon_redemptions",
    )
    order = models.ForeignKey(
        "orders.Order",
        verbose_name=_("Order"),
        on_delete=models.PROTECT,
        related_name="coupon_redemptions",
    )
    redeemed_at = models.DateTimeField(
        _("Redeemed At"),
        auto_now_add=True,
    )

    class Meta:
        verbose_name = _("Coupon Redemption")
        verbose_name_plural = _("Coupon Redemptions")
        ordering = ["-redeemed_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["coupon", "order"],
                name="unique_coupon_per_order",
            )
        ]

    def __str__(self) -> str:
        return f"{self.coupon} -- {self.customer} on order {self.order}"

    def __repr__(self) -> str:
        return (
            f"<CouponRedemption id={self.id} coupon={self.coupon} "
            f"customer={self.customer} order={self.order}>"
        )
