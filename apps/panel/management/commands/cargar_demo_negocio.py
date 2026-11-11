"""Carga ejemplos locales de inventario y pedidos.

No se ejecuta en migraciones, al iniciar el servidor ni en un despliegue.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.panel.demo import cargar_demo_negocio


class Command(BaseCommand):
    help = (
        "Crea, solo en desarrollo local, insumos y pedidos marcados como DEMO. "
        "Es idempotente y exige --confirmar."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirmar",
            action="store_true",
            help="Confirma que quieres escribir los ejemplos en la base local.",
        )

    def handle(self, *args, **options):
        motor = settings.DATABASES["default"].get("ENGINE", "")
        if not settings.DEBUG or motor != "django.db.backends.sqlite3":
            raise CommandError(
                "Bloqueado. Este comando solo corre con DEBUG activo y SQLite local. "
                "No se escribió nada."
            )
        if not options["confirmar"]:
            raise CommandError("Falta --confirmar. No se escribió nada.")
        try:
            resultado = cargar_demo_negocio()
        except ValidationError as exc:
            raise CommandError(" ".join(exc.messages)) from exc
        self.stdout.write(
            f"Insumos de ejemplo revisados: {resultado['insumos']}. "
            f"Pedidos de demostración nuevos: {resultado['pedidos_nuevos']}."
        )
        if not resultado["con_producto"]:
            self.stdout.write(
                "No hay un pie de limón con precio minorista, así que no se crearon pedidos."
            )
        self.stdout.write(
            "Las cantidades son ejemplos de prueba. No son la receta ni el stock del taller."
        )
