"""Ensayo local de serialización e integridad del catálogo, nunca de datos personales.
Uso: python scripts/ensayar_catalogo.py --origen db.sqlite3
La fuente se abre de solo lectura; el destino y la fixture viven en un temporal.
No verifica PostgreSQL ni importa a Neon.
"""
from contextlib import closing
import argparse
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
MODELOS = ("Categoria", "Producto", "VarianteProducto", "ElementoGaleria")


def worker(modo, base, fixture):
    if modo == "importar" and base.exists():
        raise ValueError("El destino del ensayo debe ser nuevo; no se sobrescriben bases existentes.")
    sys.path.insert(0,str(ROOT))
    for clave in list(os.environ):
        if clave.startswith(("DJANGO_", "VERCEL", "NEGOCIO_")) or clave == "DATABASE_URL":
            os.environ.pop(clave)
    os.environ.update(DJANGO_SETTINGS_MODULE="config.settings", DJANGO_DEBUG="1", DJANGO_LOAD_ENV="0")
    from django.conf import settings
    settings.DATABASES["default"]["NAME"] = base.as_uri()+"?mode=ro" if modo == "exportar" else str(base)
    settings.DATABASES["default"]["OPTIONS"] = {"uri":True} if modo == "exportar" else {}
    import django
    django.setup()
    from django.core.management import call_command
    from django.core import serializers
    from django.apps import apps
    from django.db import connection
    if modo == "exportar":
        with fixture.open("x", encoding="utf-8") as salida:
            call_command("dumpdata","catalogo",stdout=salida,verbosity=0)
        return
    call_command("migrate",interactive=False,verbosity=0)
    call_command("loaddata",str(fixture),verbosity=0)
    connection.check_constraints()
    def normalizar(filas):
        return sorted(filas,key=lambda x:(x["model"],x["pk"]))
    original=json.loads(fixture.read_text(encoding="utf-8"))
    objetos=[obj for nombre in MODELOS for obj in apps.get_model("catalogo",nombre).objects.all()]
    restaurado=json.loads(serializers.serialize("json",objetos))
    assert normalizar(original)==normalizar(restaurado), "Los datos restaurados no coinciden"
    from django.contrib.staticfiles import finders
    faltantes=0
    for nombre in ("Producto","ElementoGaleria"):
        for obj in apps.get_model("catalogo",nombre).objects.all():
            referencia=obj.referencia_imagen
            if referencia and not finders.find(referencia): faltantes+=1
    assert faltantes==0, "Hay referencias de fotos sin archivo estático"
    print(json.dumps({nombre:apps.get_model("catalogo",nombre).objects.count() for nombre in MODELOS}))
    print("OK: catálogo idéntico, relaciones válidas y fotografías disponibles en destino aislado SQLite.")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origen",type=Path)
    parser.add_argument("--worker",choices=("exportar","importar"),help=argparse.SUPPRESS)
    parser.add_argument("--base",type=Path,help=argparse.SUPPRESS)
    parser.add_argument("--fixture",type=Path,help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.worker:
        worker(args.worker,args.base.resolve(),args.fixture.resolve())
        return
    if not args.origen or not args.origen.is_file(): parser.error("Indica una base SQLite existente con --origen.")
    with tempfile.TemporaryDirectory(prefix="suspiro-b14-catalogo-") as carpeta:
        temporal=Path(carpeta)
        copia=temporal/"origen-copia.sqlite3"
        with closing(sqlite3.connect(args.origen.resolve().as_uri()+"?mode=ro",uri=True)) as origen, closing(sqlite3.connect(copia)) as destino:
            origen.backup(destino)
        fixture=temporal/"catalogo.json"
        for modo,base in (("exportar",copia),("importar",temporal/"ensayo.sqlite3")):
            subprocess.run([sys.executable,str(Path(__file__).resolve()),"--worker",modo,"--base",str(base),"--fixture",str(fixture)],cwd=ROOT,check=True)
    print("La base original no se modificó. El temporal del ensayo se retiró.")


if __name__ == "__main__":
    main()
