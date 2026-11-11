from django.core.management.base import BaseCommand, CommandError

from apps.catalogo.rollitos import ErrorRollitos, cargar_rollitos


class Command(BaseCommand):
    help = (
        "Crea Rollitos de sabores y la galería de los siete sabores, "
        "sin volver a importar los 26 productos ni escribir precios."
    )

    def handle(self, *args, **options):
        try:
            resultado = cargar_rollitos()
        except ErrorRollitos as exc:
            raise CommandError(str(exc)) from exc
        estado = "creado" if resultado["creado"] else "ya existía"
        portada = "provisional" if resultado["provisional"] else "definitiva"
        self.stdout.write(f"Producto {resultado['slug']}: {estado}.")
        self.stdout.write(f"Portada {portada}: {resultado['portada']}.")
        self.stdout.write(f"Fotografías de la galería: {resultado['galeria']}.")
        if resultado["provisional"]:
            self.stdout.write(
                "Cuando exista static/imagenes/rollossabores.png, "
                "vuelve a ejecutar este comando para reemplazar solo la portada."
            )
