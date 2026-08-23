from django.db import models


class FulfilmentStatusEnum(models.TextChoices):
    PENDING = ("PENDING", "Pending Allocation")
    ALLOCATED = ("ALLOCATED", "Allocated")
    PICKED = ("PICKED", "Picked")
    PACKED = ("PACKED", "Packed")
    SHIPPED = ("SHIPPED", "Shipped")
    DELIVERED = ("DELIVERED", "Delivered")
    CANCELLED = ("CANCELLED", "Cancelled")
