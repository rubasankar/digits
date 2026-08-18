from django.db import models


class AddressChoices(models.TextChoices):
    SHIPPING = ("SHIP", "Shipping")
    BILLING = ("BILL", "Billing")
    BOTH = ("BOTH", "Both")
