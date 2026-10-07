from django.apps import AppConfig

from . import __version__


class ShipyardConfig(AppConfig):
    name = "shipyard"
    label = "shipyard"
    verbose_name = f"Shipyard v{__version__}"
    default_auto_field = "django.db.models.BigAutoField"
