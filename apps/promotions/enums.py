from django.db import models


class DiscountTypeEnum(models.TextChoices):
    PERCENTAGE = ("PERCENTAGE", "Percentage")
    FIXED = ("FIXED", "Fixed Amount")
    FREE_SHIPPING = ("FREE_SHIPPING", "Free Shipping")


class ApplyTypeEnum(models.TextChoices):
    CART = ("CART", "Entire Cart")
    PRODUCT = ("PRODUCT", "Specific Product")
    CATEGORY = ("CATEGORY", "Product Category")
    VARIANT = ("VARIANT", "Specific Variant")
