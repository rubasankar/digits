from django.db import models


class GenderChoices(models.TextChoices):
    MALE = ("M", "Male")
    FEMALE = ("F", "Female")
    OTHER = ("O", "Other")
    PREFER_NOT_TO_SAY = ("N", "Prefer Not to Say")
