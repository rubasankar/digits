from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class StaffConfig(AppConfig):
    name = "apps.staff"
    verbose_name = _("Staff")

    def ready(self) -> None:
        import apps.staff.signals  # noqa: F401,PLC0415
