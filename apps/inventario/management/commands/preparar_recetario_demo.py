import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, DatabaseError

from apps.inventario.recetario_demo import preparar_plan, guardar_recetario, verificar_local


def respaldar_local():
    fuente = Path(connection.settings_dict["NAME"]).resolve()
    if fuente != (settings.BASE_DIR / "db.sqlite3").resolve() or not fuente.is_file():
        raise CommandError("La escritura requiere el archivo SQLite local del proyecto, para respaldarlo de forma consistente.")
    carpeta = settings.BASE_DIR / "respaldos_locales"
    carpeta.mkdir(exist_ok=True)
    destino = carpeta / f"antes-recetario-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:8]}.sqlite3"
    with destino.open("xb"):
        pass
    with sqlite3.connect(fuente.as_uri() + "?mode=ro", uri=True) as origen, sqlite3.connect(destino) as copia:
        origen.backup(copia)
        if copia.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise CommandError("Falló la integridad del respaldo. No se cargó el recetario.")
    return destino


class Command(BaseCommand):
    help = "Valida y revisa un recetario DEMO local. Sin --guardar no escribe datos."
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("archivo", type=Path)
        parser.add_argument("--guardar", action="store_true")
        parser.add_argument("--confirmar", action="store_true")
        parser.add_argument("--revision")

    def handle(self, *args, **options):
        try:
            verificar_local()  # Antes de consultar cualquier tabla.
            if options["guardar"] and (not options["confirmar"] or not options["revision"]):
                raise CommandError("Guardar requiere --confirmar y --revision obtenida en la vista previa.")
            archivo = options["archivo"]
            if archivo.stat().st_size > 2_000_000:
                raise CommandError("El recetario supera el tamaño admitido.")
            datos = json.loads(archivo.read_text(encoding="utf-8-sig"))
            plan = preparar_plan(datos)
            self.stdout.write("VISTA PREVIA — Recetas referenciales, provisionales; pendientes de validación por la dueña.")
            for fila in plan["recetas"]:
                self.stdout.write(f"{fila['alcance']} · {fila['producto']} · {fila['presentacion'] or 'Principal'} · rendimiento {fila['rendimiento']} presentaciones · {'sin cambios' if fila['ya_existe'] else 'nueva'}")
                for ingrediente in fila["ingredientes"]:
                    insumo = plan["insumos"][ingrediente["insumo"]]
                    self.stdout.write(f"  {insumo['nombre']}: {ingrediente['cantidad']} {insumo['unidad']}")
            nuevos = sum(i["id_existente"] is None for i in plan["insumos"].values())
            self.stdout.write(f"Insumos necesarios nuevos: {nuevos}; existentes reutilizados: {len(plan['insumos'])-nuevos}. No se alteran sus unidades ni existencias.")
            self.stdout.write(f"Revisión: {plan['revision']}")
            if not options["guardar"]:
                self.stdout.write("Solo revisión. No se guardó nada. Rollitos permanece bloqueado.")
                return
            if plan["revision"] != options["revision"]:
                raise CommandError("La revisión cambió. No se guardó nada; revisa de nuevo.")
            respaldo = respaldar_local()
            guardar_recetario(datos, options["revision"])
            self.stdout.write(f"Definiciones DEMO guardadas. Respaldo privado: {respaldo.name}. No se generaron compras, movimientos ni existencias positivas.")
        except (ValidationError, DatabaseError, OSError, ValueError, TypeError, KeyError) as exc:
            mensaje = " ".join(exc.messages) if isinstance(exc, ValidationError) else "No se pudo validar o guardar. Revisa el formato y el entorno local; si hubo un error durante la escritura, la transacción se revirtió."
            raise CommandError(mensaje) from exc
