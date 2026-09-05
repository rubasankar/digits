from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AccountsConfig(AppConfig):
    name = "apps.accounts"
    verbose_name = _("User Accounts")

    def ready(self) -> None:
        import apps.accounts.signals  # noqa: F401,PLC0415
