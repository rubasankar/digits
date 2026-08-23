from django.db import models


class CartType(models.TextChoices):
    ACTIVE = ("ACTIVE", "Active Cart")
    SAVED = ("SAVED", "Saved for Later")
    BUY_NOW = ("BUY_NOW", "Buy Now")
    MERGED = ("MERGED", "Merged (guest cart archived after login)")
