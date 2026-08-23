from typing import TYPE_CHECKING
from typing import Any
from typing import cast
from typing import override

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from .models import StaffDepartment
from .models import StaffProfile

if TYPE_CHECKING:
    from typing import Any
    from typing import ClassVar

    from django import forms
    from django.db.models import QuerySet
    from django.http import HttpRequest

    from apps.accounts.models import UserAccount


@admin.register(StaffDepartment)
class StaffDepartmentAdmin(ModelAdmin):  # type: ignore[misc]
    list_display = ["name", "is_active", "display_order"]
    list_filter = ["is_active"]
    search_fields = ["name"]
    readonly_fields = ["created", "modified"]
    fieldsets = (
        (None, {"fields": ("name", "description")}),
        (
            _("Visibility"),
            {
                "fields": ("is_active", "display_order"),
                "description": _(
                    "Inactive departments are hidden from the staff profile form "
                    "but existing assignments are preserved."
                ),
            },
        ),
        (
            _("Timestamps"),
            {"fields": ("created", "modified"), "classes": ("collapse",)},
        ),
    )


@admin.register(StaffProfile)
class StaffProfileAdmin(ModelAdmin):  # type: ignore[misc]
    list_display = [
        "full_name",
        "user",
        "department",
        "role",
        "phone_number",
        "is_active",
    ]
    list_filter = ["department", "is_active"]
    search_fields = ["first_name", "last_name", "user__email", "role"]
    readonly_fields = ["created", "modified"]
    fieldsets = (
        (None, {"fields": ("user", "first_name", "last_name")}),
        (_("Role"), {"fields": ("role", "department", "avatar")}),
        (_("Contact"), {"fields": ("phone_number",)}),
        (
            _("Access"),
            {
                "fields": ("is_active",),
                "description": _(
                    "Deactivating here revokes staff dashboard access. "
                    "Also disable the UserAccount to block all login."
                ),
            },
        ),
        (
            _("Internal Notes"),
            {
                "fields": ("notes",),
                "classes": ("collapse",),
                "description": _(
                    "Visible to admins only -- not shown to the staff member."
                ),
            },
        ),
        (
            _("Timestamps"),
            {"fields": ("created", "modified"), "classes": ("collapse",)},
        ),
    )
    SELF_SERVICE_FIELDSETS: ClassVar[tuple[tuple[str | None, dict[str, Any]], ...]] = (
        (None, {"fields": ("first_name", "last_name", "avatar", "phone_number")}),
    )

    def get_fieldsets(
        self, request: HttpRequest, obj: StaffProfile | None = None
    ) -> Any:
        if getattr(request.user, "is_superuser", False):
            return super().get_fieldsets(request, obj)
        return self.SELF_SERVICE_FIELDSETS

    def has_view_permission(
        self, request: HttpRequest, obj: StaffProfile | None = None
    ) -> bool:
        if super().has_view_permission(request, obj):
            return True
        return self._is_own_profile(request, obj)

    @staticmethod
    def _is_own_profile(request: HttpRequest, obj: StaffProfile | None) -> bool:
        user = getattr(request, "user", None)
        if obj is None:
            return bool(getattr(user, "is_staff", False))
        return bool(obj.user_id == cast("UserAccount", user).pk)

    def get_queryset(self, request: HttpRequest) -> QuerySet[StaffProfile]:
        qs = cast("QuerySet[StaffProfile]", super().get_queryset(request))
        user = cast("UserAccount", request.user)
        if getattr(user, "is_superuser", False):
            return qs
        return qs.filter(user=user)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return bool(getattr(request.user, "is_superuser", False))

    def has_delete_permission(
        self, request: HttpRequest, obj: StaffProfile | None = None
    ) -> bool:
        return bool(getattr(request.user, "is_superuser", False))

    @override
    def save_model(
        self,
        request: HttpRequest,
        obj: StaffProfile,
        form: forms.ModelForm[Any],
        change: bool,
    ) -> None:
        try:
            obj.full_clean()
        except ValidationError as exc:
            form._update_errors(exc)  # type: ignore[attr-defined]  # noqa: SLF001
            return
        super().save_model(request, obj, form, change)
