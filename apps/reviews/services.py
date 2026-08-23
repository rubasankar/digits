from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from apps.orders.enums import OrderStatusEnum
from apps.orders.models import OrderItem
from core.exceptions import PermissionDeniedError
from core.models import GlobalSettings

from .models import ProductReview

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from apps.catalogue.models.product import Product
    from apps.customers.models import CustomerProfile


@dataclass(frozen=True, slots=True)
class ReviewDraft:
    """Customer-supplied content for a new review."""

    title: str = ""
    body: str = ""
    order_item: OrderItem | None = None


class ReviewService:
    # Submit - customer-facing

    @classmethod
    @transaction.atomic
    def submit(
        cls,
        *,
        product: Product,
        customer: CustomerProfile,
        rating: int,
        draft: ReviewDraft,
    ) -> ProductReview:
        # 1. Duplicate guard
        if ProductReview.objects.filter(customer=customer, product=product).exists():
            raise ValidationError(
                _("You have already submitted a review for this product.")
            )

        # 2. Order item ownership
        if draft.order_item is not None:
            cls._validate_order_item_ownership(draft.order_item, customer)

        # 3. Verified purchase
        is_verified = cls._check_verified_purchase(
            product=product,
            customer=customer,
            order_item=draft.order_item,
        )

        # 4. Auto-publish
        is_published = GlobalSettings.get().auto_publish_reviews

        # 5. Create
        review = ProductReview(
            product=product,
            customer=customer,
            order_item=draft.order_item,
            rating=rating,
            title=draft.title,
            body=draft.body,
            is_verified_purchase=is_verified,
            # Set explicitly here so model.save() auto-publish is a no-op
            # (pk is None but is_published is already True when applicable).
            is_published=is_published,
        )
        review.full_clean()
        review.save()

        return review

    # Moderation - staff-facing

    @classmethod
    @transaction.atomic
    def publish(cls, review: ProductReview) -> ProductReview:
        """Make a review visible on the storefront."""
        if review.is_published:
            return review  # idempotent
        review.is_published = True
        review.save(update_fields=["is_published", "modified"])
        return review

    @classmethod
    @transaction.atomic
    def unpublish(cls, review: ProductReview) -> ProductReview:
        """Hide a review from the storefront without deleting it."""
        if not review.is_published:
            return review  # idempotent
        review.is_published = False
        review.save(update_fields=["is_published", "modified"])
        return review

    @classmethod
    @transaction.atomic
    def bulk_publish(
        cls,
        queryset: QuerySet[ProductReview],
    ) -> int:
        """
        Publish a queryset of reviews in a single UPDATE statement.

        Returns the number of rows updated.
        Intended for admin bulk actions.
        """
        return queryset.filter(is_published=False).update(is_published=True)

    @classmethod
    @transaction.atomic
    def bulk_unpublish(
        cls,
        queryset: QuerySet[ProductReview],
    ) -> int:
        """Unpublish a queryset of reviews in a single UPDATE statement."""
        return queryset.filter(is_published=True).update(is_published=False)

    # Verification

    @classmethod
    @transaction.atomic
    def verify_purchase(cls, review: ProductReview) -> ProductReview:
        """
        Mark a review as a verified purchase.

        Call this when an order containing the reviewed product is confirmed
        as DELIVERED and the review does not yet have is_verified_purchase=True.
        """
        if review.is_verified_purchase:
            return review
        review.is_verified_purchase = True
        review.save(update_fields=["is_verified_purchase", "modified"])
        return review

    # Internal helpers

    @classmethod
    def _validate_order_item_ownership(
        cls,
        order_item: OrderItem,
        customer: CustomerProfile,
    ) -> None:
        """
        Raise PermissionDeniedError when order_item does not belong to customer.
        Uses a single DB query; does not re-raise DoesNotExist (FK integrity
        is handled by the DB).
        """

        owner_id = (
            OrderItem.objects.filter(pk=order_item.pk)
            .values_list("order__customer_id", flat=True)
            .first()
        )
        if owner_id is None:
            # FK row gone - not our concern here.
            return
        if owner_id != customer.pk:
            raise PermissionDeniedError(
                str(_("The order item does not belong to this customer."))
            )

    @classmethod
    def _check_verified_purchase(
        cls,
        *,
        product: Product,
        customer: CustomerProfile,
        order_item: OrderItem | None,
    ) -> bool:
        """
        Return True when the customer has a verified purchase of the product.

        Fast path: if order_item is provided and ownership was already
        validated, return True immediately - no extra query needed.

        Slow path: scan the customer's DELIVERED order history for this product.
        """

        # Fast path via direct order_item link.
        if order_item is not None:
            return True

        # Slow path: any DELIVERED order containing this product.
        return OrderItem.objects.filter(
            order__customer=customer,
            order__status=OrderStatusEnum.DELIVERED,
            variant__product=product,
        ).exists()
