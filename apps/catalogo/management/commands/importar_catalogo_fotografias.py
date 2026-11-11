from django.core.management.base import BaseCommand, CommandError

from apps.catalogo.importacion import ErrorImportacion, importar_catalogo


class Command(BaseCommand):
    help = (
        "Importa las 7 categorías y los 26 productos con fotografía. "
        "Con --dry-run solo muestra el plan."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Valida y muestra el plan sin escribir en la base.",
        )

    def handle(self, *args, **options):
        try:
            plan = importar_catalogo(dry_run=options["dry_run"])
        except ErrorImportacion as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            f"Categorías nuevas: {len(plan['categorias_nuevas'])}. "
            f"Reutilizadas: {len(plan['categorias_reutilizadas'])}."
        )
        self.stdout.write(
            f"Productos nuevos: {len(plan['productos_nuevos'])}. "
            f"Ya compatibles: {len(plan['productos_compatibles'])}."
        )
        for slug in plan["productos_nuevos"]:
            self.stdout.write(f"  crear {slug}")
        for slug in plan["productos_compatibles"]:
            self.stdout.write(f"  conservar {slug}")
        if options["dry_run"]:
            self.stdout.write("No se escribió en la base de datos.")
        else:
            self.stdout.write("Importación completada.")
