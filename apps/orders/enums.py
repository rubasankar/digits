from django.db import models


class OrderStatusEnum(models.TextChoices):
    PENDING = ("PENDING", "Pending")
    CONFIRMED = ("CONFIRMED", "Confirmed")
    PROCESSING = ("PROCESSING", "Processing")
    SHIPPED = ("SHIPPED", "Shipped")
    DELIVERED = ("DELIVERED", "Delivered")
    CANCELLED = ("CANCELLED", "Cancelled")
    RETURN_REQUESTED = ("RETURN_REQUESTED", "Return Requested")
    RETURNED = ("RETURNED", "Returned")


class ReturnRequestStatusEnum(models.TextChoices):
    PENDING = ("PENDING", "Pending Review")
    APPROVED = ("APPROVED", "Approved")
    REJECTED = ("REJECTED", "Rejected")
    RETURN_SHIPPED = ("RETURN_SHIPPED", "Return Shipped by Customer")
    RECEIVED = ("RECEIVED", "Items Received at Warehouse")
    COMPLETED = ("COMPLETED", "Completed")
    CANCELLED = ("CANCELLED", "Cancelled by Customer")


class ReturnReasonEnum(models.TextChoices):
    DAMAGED = ("DAMAGED", "Item Arrived Damaged")
    WRONG_ITEM = ("WRONG_ITEM", "Wrong Item Received")
    NOT_AS_DESCRIBED = ("NOT_AS_DESCRIBED", "Not as Described")
    CHANGED_MIND = ("CHANGED_MIND", "Changed My Mind")
    DEFECTIVE = ("DEFECTIVE", "Item is Defective / Not Working")
    MISSING_PARTS = ("MISSING_PARTS", "Missing Parts or Accessories")
    OTHER = ("OTHER", "Other")
