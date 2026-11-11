from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from config.base_datos import configurar_base


class SeleccionBaseDatosTests(SimpleTestCase):
    def test_sin_url_conserva_sqlite(self):
        ruta = Path("db.sqlite3")
        for valor in ("", "   ", None):
            config = configurar_base(valor, ruta)
            self.assertEqual(config["ENGINE"], "django.db.backends.sqlite3")
            self.assertEqual(config["NAME"], ruta)

    def test_postgres_toma_la_url_sin_abrir_conexion(self):
        clave = "clave-de-prueba-no-real"
        url = f"postgresql://duena:{clave}@db.ejemplo.interno:5432/suspiro?sslmode=require"
        config = configurar_base(url, Path("db.sqlite3"))
        self.assertEqual(config["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(config["NAME"], "suspiro")
        self.assertEqual(config["USER"], "duena")
        self.assertEqual(config["PASSWORD"], clave)
        self.assertEqual(config["HOST"], "db.ejemplo.interno")
        self.assertEqual(config["PORT"], "5432")
        self.assertEqual(config["OPTIONS"]["sslmode"], "require")
        self.assertEqual(config["CONN_MAX_AGE"], 0)
        corto = configurar_base("postgres://duena:otra@host.ejemplo/pasteleria", Path("db.sqlite3"))
        self.assertEqual(corto["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(corto["PORT"], "5432")

    def test_un_esquema_invalido_no_revela_la_clave(self):
        with self.assertRaises(ImproperlyConfigured) as error:
            configurar_base("mysql://duena:clave-secreta@host.ejemplo/db", Path("db.sqlite3"))
        self.assertNotIn("clave-secreta", str(error.exception))

    def test_una_url_incompleta_no_revela_la_clave(self):
        with self.assertRaises(ImproperlyConfigured) as error:
            configurar_base("postgresql://duena:clave-secreta@/solo-nombre", Path("db.sqlite3"))
        self.assertNotIn("clave-secreta", str(error.exception))
