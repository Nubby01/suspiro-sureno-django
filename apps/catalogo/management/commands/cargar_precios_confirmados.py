from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.catalogo.precios_confirmados import PENDIENTES, aplicar_precios_confirmados


class Command(BaseCommand):
    help = (
        "Actualiza los precios minoristas confirmados en la base SQLite local. "
        "No crea productos ni toca el precio mayorista."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirmar",
            action="store_true",
            help="Escribe los precios. Sin esta opción el comando no modifica la base.",
        )

    def handle(self, *args, **options):
        motor = settings.DATABASES["default"]["ENGINE"]
        if motor != "django.db.backends.sqlite3":
            raise CommandError("Esta carga solo se ejecuta sobre la base SQLite local.")
        if not options["confirmar"]:
            raise CommandError("No se escribió ningún precio. Vuelve a ejecutarlo con --confirmar.")
        resultado = aplicar_precios_confirmados()
        for fila in resultado:
            self.stdout.write(f"{fila['slug']}: {fila['accion']}")
        self.stdout.write("Sin cargar:")
        for fila in PENDIENTES:
            precio = "sin precio en la lista" if fila["precio"] is None else f"${int(fila['precio'])}"
            self.stdout.write(f"{fila['asunto']} ({precio}): {fila['motivo']}")
