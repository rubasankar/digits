from django.db import models


class MovementTypeEnum(models.TextChoices):
    RECEIPT = ("RECEIPT", "Stock Receipt")
    SALE = ("SALE", "Sale / Dispatch")
    RETURN = ("RETURN", "Customer Return")
    ADJUSTMENT_IN = ("ADJ_IN", "Adjustment (Increase)")
    ADJUSTMENT_OUT = ("ADJ_OUT", "Adjustment (Decrease)")
    TRANSFER_IN = ("XFER_IN", "Transfer In")
    TRANSFER_OUT = ("XFER_OUT", "Transfer Out")
    RESERVE = ("RESERVE", "Reserve for Order")
    RELEASE = ("RELEASE", "Release Reservation")
