from django.apps import AppConfig


class PropertiesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.properties"
    label = "properties"

    def ready(self) -> None:
        from . import signals  # noqa: F401  (register signal handlers)
