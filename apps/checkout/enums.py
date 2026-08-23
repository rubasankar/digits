from django.db import models


class SessionStatus(models.TextChoices):
    ACTIVE = ("ACTIVE", "Active")
    PROCESSING = ("PROCESSING", "Processing Payment")
    COMPLETED = ("COMPLETED", "Completed")
    ABANDONED = ("ABANDONED", "Abandoned")
    FAILED = ("FAILED", "Failed")


class CheckoutStep(models.TextChoices):
    ADDRESS = ("ADDRESS", "Address")
    SHIPPING = ("SHIPPING", "Shipping Method")
    PAYMENT = ("PAYMENT", "Payment")
    CONFIRMATION = ("CONFIRMATION", "Confirmation")
