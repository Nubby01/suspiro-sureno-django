from pathlib import Path
from unittest.mock import patch
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase
from config.base_datos import configurar_base
from config.entorno import booleano, validar_hosts, validar_origenes


class ConfiguracionProduccionTests(SimpleTestCase):
    def test_produccion_no_admite_sqlite(self):
        with self.assertRaises(ImproperlyConfigured):
            configurar_base("", Path("db.sqlite3"), produccion=True)

    def test_tls_y_pooler_sin_conexion(self):
        base=configurar_base("postgresql://qa:prueba@servidor.invalid/b?channel_binding=require",Path("db.sqlite3"),produccion=True)
        self.assertEqual(base["OPTIONS"]["sslmode"],"require")
        self.assertEqual(base["OPTIONS"]["channel_binding"],"require")
        self.assertTrue(base["DISABLE_SERVER_SIDE_CURSORS"])
        self.assertEqual(base["CONN_MAX_AGE"],0)
        for modo in ("disable","allow","prefer"):
            with self.assertRaises(ImproperlyConfigured):
                configurar_base("postgresql://qa:prueba@servidor.invalid/b?sslmode="+modo,Path("db.sqlite3"),produccion=True)

    def test_url_malformada_no_revela_password(self):
        for url in ("postgresql://qa:privado@host:xyz/base", "postgresql://qa:privado@[invalido/base"):
            with self.assertRaises(ImproperlyConfigured) as error:
                configurar_base(url,Path("db.sqlite3"))
            self.assertNotIn("privado",str(error.exception))

    def test_hosts_y_origenes_explicitos(self):
        validar_hosts(["proyecto-b.invalid"],produccion=True)
        validar_origenes(["https://proyecto-b.invalid"],produccion=True)
        for hosts in ([],["*"],[".vercel.app"],["https://sitio.invalid"]):
            with self.assertRaises(ImproperlyConfigured):validar_hosts(hosts,produccion=True)
        for origenes in ([],["http://sitio.invalid"],["https://*.vercel.app"],["https://sitio.invalid/ruta"]):
            with self.assertRaises(ImproperlyConfigured):validar_origenes(origenes,produccion=True)

    def test_booleanos_explicitos(self):
        for valor, esperado in (("0",False),("False",False),("1",True),("true",True)):
            with patch.dict("os.environ",{"B14_PRUEBA":valor}):self.assertEqual(booleano("B14_PRUEBA"),esperado)
        with patch.dict("os.environ",{"B14_PRUEBA":"otro"}):
            with self.assertRaises(ImproperlyConfigured):booleano("B14_PRUEBA")
