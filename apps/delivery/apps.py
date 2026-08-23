from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class DeliveryConfig(AppConfig):
    name = "apps.delivery"
    verbose_name = _("Delivery")

    def ready(self) -> None:
        """Import handler registrations and assert all FulfilmentType values covered."""
        import apps.delivery.handlers  # noqa: F401, PLC0415
        from apps.delivery.registry import FulfilmentRoutingRegistry  # noqa: PLC0415

        FulfilmentRoutingRegistry.assert_complete()
