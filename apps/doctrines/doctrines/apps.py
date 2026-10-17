from django.apps import AppConfig

from . import __version__


class DoctrinesConfig(AppConfig):
    name = "doctrines"
    label = "doctrines"
    verbose_name = f"Doctrines v{__version__}"
    default_auto_field = "django.db.models.BigAutoField"
