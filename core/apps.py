from django.apps import AppConfig
from django.db.models.signals import post_migrate


class CoreConfig(AppConfig):
    name = 'core'
    verbose_name = 'Core'

    def ready(self):
        from . import signals  # noqa: F401  (connects the security event loggers)
        from .rls import enable_row_level_security

        # After every migrate, including the test database's.
        post_migrate.connect(enable_row_level_security, sender=self, dispatch_uid='core.rls')
