import os
import sys

from django.apps import AppConfig


class RelojesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "relojes"
    verbose_name = "Relojes"

    def ready(self):
        # No arrancar en management commands como migrate, collectstatic, etc.
        _SKIP = {"migrate", "makemigrations", "collectstatic", "shell", "test",
                 "check", "help", "inspectdb", "showmigrations", "run_scheduler"}
        if len(sys.argv) > 1 and sys.argv[1] in _SKIP:
            return

        # En runserver (con auto-reloader) solo arrancar en el proceso hijo
        if "runserver" in sys.argv and os.environ.get("RUN_MAIN") != "true":
            return

        self._conectar_signals()
        from relojes import scheduler
        scheduler.start()

    def _conectar_signals(self):
        from django.db.models.signals import post_save, post_delete
        from relojes.models import TareaProgramada
        from relojes import scheduler

        def _guardada(sender, instance, **kwargs):
            scheduler.agregar_o_actualizar(instance)

        def _eliminada(sender, instance, **kwargs):
            scheduler.eliminar(instance.id)

        post_save.connect(_guardada, sender=TareaProgramada, weak=False)
        post_delete.connect(_eliminada, sender=TareaProgramada, weak=False)
