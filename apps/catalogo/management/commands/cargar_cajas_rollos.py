from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.catalogo.cajas import aplicar_cajas_faltantes


class Command(BaseCommand):
    help = "Completa las cajas de rollos que siguen sin precio. No sobrescribe precios existentes."

    def add_arguments(self, parser):
        parser.add_argument("--confirmar", action="store_true")

    def handle(self, *args, **options):
        if settings.DATABASES["default"]["ENGINE"] != "django.db.backends.sqlite3":
            raise CommandError("Esta carga solo se ejecuta sobre la base SQLite local.")
        if not options["confirmar"]:
            raise CommandError("No se escribió ningún precio. Vuelve a ejecutarlo con --confirmar.")
        for fila in aplicar_cajas_faltantes():
            self.stdout.write(f"{fila['slug']}: {fila['accion']}")
