from typing import TYPE_CHECKING
from typing import Any
from typing import cast

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from .models import StaffDepartment
from .models import StaffProfile

if TYPE_CHECKING:
    from typing import Any
    from typing import ClassVar

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
        "is_active",
    ]
    list_filter = ["department", "is_active"]
    search_fields = ["first_name", "last_name", "user__email", "role"]
    readonly_fields = ["created", "modified", "avatar_display"]
    fieldsets = (
        (None, {"fields": ("user", "first_name", "last_name")}),
        (_("Role"), {"fields": ("role", "department")}),
        (
            _("Avatar"),
            {"fields": ("avatar", "avatar_display"), "classes": ("collapse",)},
        ),
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
        (
            None,
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "avatar",
                    "avatar_display",
                )
            },
        ),
    )

    def formfield_for_foreignkey(
        self, db_field: Any, request: HttpRequest, **kwargs: Any
    ) -> Any:
        if db_field.name == "department":
            # Inactive departments are hidden from the dropdown, but keep the
            # currently-assigned one visible even if it was since deactivated.
            qs = StaffDepartment.objects.filter(is_active=True)
            object_id = (
                request.resolver_match.kwargs.get("object_id")
                if request.resolver_match
                else None
            )
            if object_id:
                qs = qs | StaffDepartment.objects.filter(staff__pk=object_id)
            kwargs["queryset"] = qs.distinct()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

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

    @admin.display(description=_("Avatar"))
    def avatar_display(self, obj: StaffProfile) -> str:
        if obj.avatar:
            return format_html(
                '<img src="{}" style="max-height: 150px; border-radius: 8px;" />',
                obj.avatar.url,
            )
        return str(_("No avatar uploaded"))

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
