from django.core.management.base import BaseCommand

from apps.catalogo.precios_comerciales import (
    AMBIGUOS,
    AUSENTES,
    VARIANTES_NO_CREADAS,
    revisar_propuestas,
)


class Command(BaseCommand):
    help = "Muestra la vista previa de precios comerciales. No escribe en la base."

    def handle(self, *args, **options):
        self.stdout.write("Vista previa. No se escribió ningún precio.")
        for fila in revisar_propuestas():
            self.stdout.write(
                f"{fila['codigo']} {fila['slug']}: minorista {fila['minorista']} — {fila['estado']} — {fila['accion']}"
            )
        self.stdout.write("Ambiguos, sin carga:")
        for fila in AMBIGUOS:
            self.stdout.write(f"{fila['codigo']} {fila['slug']}: {fila['motivo']}")
        self.stdout.write("Sin producto fotografiado, sin alta:")
        for nombre in AUSENTES:
            self.stdout.write(nombre)
        self.stdout.write("Variantes no creadas:")
        for fila in VARIANTES_NO_CREADAS:
            self.stdout.write(f"{fila['codigo']} {fila['nombre']}: {fila['motivo']}")
