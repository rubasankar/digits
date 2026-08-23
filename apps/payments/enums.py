from django.db import models


class PaymentStatusEnum(models.TextChoices):
    PENDING = ("PENDING", "Pending")
    PROCESSING = ("PROCESSING", "Processing")
    REQUIRES_ACTION = ("REQUIRES_ACTION", "Requires Action")
    UNPAID = ("UNPAID", "Unpaid")
    PARTIALLY_PAID = ("PARTIALLY_PAID", "Partially Paid")
    PAID = ("PAID", "Paid")
    FAILED = ("FAILED", "Failed")
    CANCELLED = ("CANCELLED", "Cancelled")
    REFUNDED = ("REFUNDED", "Refunded")
    PARTIALLY_REFUNDED = ("PARTIALLY_REFUNDED", "Partially Refunded")


class RefundStatusEnum(models.TextChoices):
    PENDING = ("PENDING", "Pending")
    PROCESSING = ("PROCESSING", "Processing")
    REFUNDED = ("REFUNDED", "Refunded")
    FAILED = ("FAILED", "Failed")
