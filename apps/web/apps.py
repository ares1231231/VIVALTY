from django.apps import AppConfig


class WebConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.web"
    label = "web"

    def ready(self) -> None:
        from . import signals  # noqa: F401
        from .staff_alerts import patch_admin_site

        patch_admin_site()
