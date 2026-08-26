from typing import TYPE_CHECKING

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from .models import ProductReview
from .services import ReviewService

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.http import HttpRequest


@admin.register(ProductReview)
class ProductReviewAdmin(ModelAdmin):  # type: ignore[misc]
    list_display = [
        "product",
        "customer",
        "rating",
        "title",
        "is_verified_purchase",
        "is_published",
        "created",
    ]
    list_filter = ["is_published", "is_verified_purchase", "rating"]
    search_fields = [
        "product__name",
        "customer__user__email",
        "customer__first_name",
        "title",
        "body",
    ]
    readonly_fields = ["created", "modified", "is_verified_purchase"]
    list_select_related = ["product", "customer"]
    actions = ["publish_reviews", "unpublish_reviews"]
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "product",
                    "customer",
                    "order_item",
                    "rating",
                    "title",
                    "body",
                )
            },
        ),
        (
            _("Moderation"),
            {
                "fields": ("is_published", "is_verified_purchase"),
                "description": _(
                    "Toggle 'Published' to control storefront visibility. "
                    "Use the bulk actions to publish or unpublish multiple reviews."
                ),
            },
        ),
        (
            _("Timestamps"),
            {"fields": ("created", "modified"), "classes": ("collapse",)},
        ),
    )

    @admin.action(description=_("Publish selected reviews"))
    def publish_reviews(
        self, request: HttpRequest, queryset: QuerySet[ProductReview]
    ) -> None:
        updated = ReviewService.bulk_publish(queryset)
        self.message_user(
            request, _("%(count)d review(s) published.") % {"count": updated}
        )

    @admin.action(description=_("Unpublish selected reviews"))
    def unpublish_reviews(
        self, request: HttpRequest, queryset: QuerySet[ProductReview]
    ) -> None:
        updated = ReviewService.bulk_unpublish(queryset)
        self.message_user(
            request, _("%(count)d review(s) unpublished.") % {"count": updated}
        )
