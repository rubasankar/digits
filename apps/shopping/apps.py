from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ShoppingConfig(AppConfig):
    name = "apps.shopping"
    verbose_name = _("Shopping")

    def ready(self) -> None:
        import apps.shopping.signals  # noqa: F401,PLC0415
