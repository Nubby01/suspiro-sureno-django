"""Respaldo consistente con SQLite backup API; nunca sobrescribe el destino."""
import argparse
from contextlib import closing
from hashlib import sha256
from pathlib import Path
import sqlite3


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origen",type=Path,required=True)
    parser.add_argument("--destino",type=Path,required=True)
    args=parser.parse_args()
    origen=args.origen.resolve();destino=args.destino.resolve()
    if not origen.is_file():parser.error("La base de origen no existe.")
    if origen==destino or destino.exists():parser.error("El destino debe ser nuevo y distinto del origen.")
    destino.parent.mkdir(parents=True,exist_ok=True)
    with destino.open("xb"):
        pass
    with closing(sqlite3.connect(origen.as_uri()+"?mode=ro",uri=True)) as fuente, closing(sqlite3.connect(destino)) as copia:
        fuente.backup(copia)
        assert copia.execute("PRAGMA integrity_check").fetchall()==[("ok",)], "Respaldo no íntegro: no usar"
    print("Respaldo íntegro creado. SHA-256: "+sha256(destino.read_bytes()).hexdigest())
    print("Contiene datos privados. No subir a GitHub ni Vercel.")


if __name__ == "__main__":
    main()
