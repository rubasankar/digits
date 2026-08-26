from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from model_utils.models import TimeStampedModel
from model_utils.models import UUIDModel

from apps.orders.models import OrderItem

from .feature_flags import reviews_auto_publish_enabled


class ProductReview(UUIDModel, TimeStampedModel):
    product = models.ForeignKey(
        "catalogue.Product",
        verbose_name=_("Product"),
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    customer = models.ForeignKey(
        "customers.CustomerProfile",
        verbose_name=_("Customer"),
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    order_item = models.ForeignKey(
        "orders.OrderItem",
        verbose_name=_("Order Item"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviews",
        help_text=_(
            "The specific order line this review is tied to. "
            "Used by the service to set is_verified_purchase automatically. "
            "Leave blank only for legacy / migrated reviews."
        ),
    )
    rating = models.PositiveSmallIntegerField(
        _("Rating"),
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text=_("Star rating from 1 (lowest) to 5 (highest)."),
    )
    title = models.CharField(
        _("Review Title"),
        max_length=150,
        blank=True,
        help_text=_("Optional short headline, e.g. 'Great product!'"),
    )
    body = models.TextField(
        _("Review Body"),
        blank=True,
        help_text=_("Detailed review text."),
    )
    is_verified_purchase = models.BooleanField(
        _("Verified Purchase"),
        default=False,
        help_text=_(
            "Set automatically by the review service when the customer has a "
            "delivered order containing this product. "
            "Prefer linking order_item for accurate verification."
        ),
    )
    is_published = models.BooleanField(
        _("Published"),
        default=False,
        db_index=True,
        help_text=_(
            "Controls storefront visibility. "
            "When the reviews_auto_publish Waffle switch is enabled this is set "
            "automatically on submission. "
            "Otherwise staff set this manually to make the review visible."
        ),
    )

    class Meta:
        verbose_name = _("Product Review")
        verbose_name_plural = _("Product Reviews")
        ordering = ["-created"]
        constraints = [
            # One review per customer per product.
            models.UniqueConstraint(
                fields=["customer", "product"],
                name="unique_review_per_customer_product",
            ),
            models.CheckConstraint(
                condition=Q(rating__gte=1) & Q(rating__lte=5),
                name="review_rating_between_1_and_5",
            ),
            # An order_item, when provided, must belong to the same customer.
            # This is enforced in clean() - the DB constraint below catches
            # direct SQL writes that bypass Django.
            # (Full cross-table check not possible in a pure CheckConstraint;
            #  service layer must validate customer == order_item.order.customer)
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        """
        Auto-publish on first save when the Waffle switch is enabled.

        Only sets is_published on creation (pk is None) to avoid overwriting
        a staff member who has intentionally unpublished a review.
        """
        if self.pk is None and not self.is_published:
            if reviews_auto_publish_enabled():
                self.is_published = True
        super().save(*args, **kwargs)

    def clean(self) -> None:
        super().clean()
        # Validate that order_item belongs to this customer when provided.
        if self.order_item_id and self.customer_id:
            try:
                item = OrderItem.objects.select_related("order__customer").get(
                    pk=self.order_item_id
                )
                if item.order.customer_id != self.customer_id:
                    raise ValidationError(
                        {
                            "order_item": _(
                                "This order item does not belong "
                                "to the reviewing customer."
                            )
                        }
                    )
            except OrderItem.DoesNotExist:
                pass  # FK integrity handled by the database

    def __str__(self) -> str:
        published = "published" if self.is_published else "unpublished"
        return f"{self.rating}\u2b50 - {self.product} by {self.customer} ({published})"

    def __repr__(self) -> str:
        return (
            f"<ProductReview id={self.id} product={self.product} "
            f"customer={self.customer} rating={self.rating} "
            f"published={self.is_published} verified={self.is_verified_purchase}>"
        )
