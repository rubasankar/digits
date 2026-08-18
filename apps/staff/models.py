from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from model_utils.models import TimeStampedModel
from model_utils.models import UUIDModel
from phonenumber_field.modelfields import PhoneNumberField

User = get_user_model()


class StaffDepartment(UUIDModel, TimeStampedModel):
    name = models.CharField(
        _("Department Name"),
        max_length=100,
        unique=True,
        help_text=_("e.g. 'Warehouse & Fulfilment', 'Customer Support'."),
    )
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Optional description of what this department does."),
    )
    is_active = models.BooleanField(
        _("Active"),
        default=True,
        help_text=_(
            "Inactive departments are hidden from the staff profile form "
            "but existing assignments are preserved."
        ),
    )
    display_order = models.PositiveSmallIntegerField(
        _("Display Order"),
        default=0,
        help_text=_("Controls order in dropdowns. Lower = first."),
    )

    class Meta:
        verbose_name = _("Staff Department")
        verbose_name_plural = _("Staff Departments")
        ordering = ["display_order", "name"]

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<StaffDepartment id={self.id} name={self.name!r}>"


class StaffProfile(UUIDModel, TimeStampedModel):
    user = models.OneToOneField(
        User,
        verbose_name=_("User Account"),
        on_delete=models.CASCADE,
        related_name="staff_profile",
        help_text=_("The linked UserAccount must have is_staff=True."),
    )
    first_name = models.CharField(_("First Name"), max_length=100)
    last_name = models.CharField(_("Last Name"), max_length=100, blank=True)
    phone_number = PhoneNumberField(
        _("Work Phone Number"),
        blank=True,
        help_text=_("Internal work contact number in E.164 format."),
    )
    role = models.CharField(
        _("Role / Job Title"),
        max_length=100,
        blank=True,
        help_text=_("e.g. 'Warehouse Manager', 'Customer Support Agent'."),
    )
    department = models.ForeignKey(
        StaffDepartment,
        verbose_name=_("Department"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff",
        help_text=_("Operational area. Manage departments in Staff - Departments."),
    )
    avatar = models.ImageField(
        _("Avatar"),
        upload_to="avatars/staff/",
        blank=True,
    )
    is_active = models.BooleanField(
        _("Staff Active"),
        default=True,
        help_text=_(
            "Deactivate to revoke staff access without deleting the account. "
            "Both this flag AND UserAccount.is_active must be True for access."
        ),
    )
    notes = models.TextField(
        _("Internal Notes"),
        blank=True,
        help_text=_("Private admin-only notes. Not visible to the staff member."),
    )

    class Meta:
        verbose_name = _("Staff Profile")
        verbose_name_plural = _("Staff Profiles")
        ordering = ["first_name", "last_name"]

    def clean(self) -> None:
        super().clean()
        if self.user and not self.user.is_staff:
            raise ValidationError(
                {
                    "user": _(
                        "A Staff Profile can only be created for an account "
                        "with is_staff=True. Enable staff access on the "
                        "UserAccount first."
                    )
                }
            )

    @property
    def full_name(self) -> str:

        return f"{self.first_name} {self.last_name}".strip()

    @property
    def display_name(self) -> str:

        if self.role:
            return f"{self.full_name} ({self.role})"
        return self.full_name

    def __str__(self) -> str:
        return self.display_name

    def __repr__(self) -> str:
        return (
            f"<StaffProfile id={self.id} user={self.user} "
            f"dept={self.department} active={self.is_active}>"
        )
