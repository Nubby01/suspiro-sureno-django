from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.catalogo.importacion import (
    CATEGORIAS,
    MANIFIESTO,
    ErrorImportacion,
    importar_catalogo,
    validar_estructura,
)
from apps.catalogo.models import Categoria, Producto, VarianteProducto
from apps.catalogo.servicios import crear_producto_con_variante_inicial


class ManifiestoTests(TestCase):
    def test_define_26_productos_y_7_categorias_sin_repetir(self):
        self.assertEqual(len(MANIFIESTO), 26)
        self.assertEqual(len(CATEGORIAS), 7)
        self.assertEqual(len({item["slug"] for item in MANIFIESTO}), 26)
        self.assertEqual(len({item["referencia_imagen"] for item in MANIFIESTO}), 26)
        self.assertEqual(len({item["slug"] for item in CATEGORIAS}), 7)
        self.assertEqual(
            [item["slug"] for item in CATEGORIAS],
            [
                "alfajores",
                "rollos-dulces",
                "rollos-salados",
                "tortas",
                "cheesecakes",
                "pies-y-kuchenes",
                "otros-dulces",
            ],
        )
        self.assertEqual(validar_estructura(MANIFIESTO, CATEGORIAS), [])

    def test_rechaza_slugs_repetidos_en_el_manifiesto(self):
        repetido = [dict(item) for item in MANIFIESTO]
        repetido[1]["slug"] = repetido[0]["slug"]
        errores = validar_estructura(repetido, CATEGORIAS)
        self.assertTrue(any("slugs de producto" in error for error in errores))


class ImportacionTests(TestCase):
    def test_dry_run_no_guarda_y_la_importacion_crea_precio_nulo(self):
        usuario = get_user_model().objects.create_user(
            username="cliente-previo",
            password="una-clave-larga-1",
        )
        previa = Categoria.objects.create(nombre="Especial", slug="especial", orden=99)
        plan = importar_catalogo(dry_run=True)
        self.assertEqual(len(plan["categorias_nuevas"]), 7)
        self.assertEqual(len(plan["productos_nuevos"]), 26)
        self.assertEqual(Producto.objects.count(), 0)
        self.assertEqual(Categoria.objects.count(), 1)

        importar_catalogo(dry_run=False)
        self.assertEqual(Categoria.objects.exclude(pk=previa.pk).count(), 7)
        self.assertEqual(Producto.objects.count(), 26)
        self.assertEqual(VarianteProducto.objects.count(), 26)
        self.assertTrue(Categoria.objects.filter(slug="especial", nombre="Especial").exists())
        usuario.refresh_from_db()
        self.assertEqual(usuario.username, "cliente-previo")
        for producto in Producto.objects.exclude(slug=""):
            self.assertEqual(producto.descripcion, "")
            self.assertTrue(producto.activo)
            self.assertTrue(producto.referencia_imagen.startswith("imagenes/catalogo-web/"))
            variante = producto.variantes.get()
            self.assertEqual(variante.nombre, "")
            self.assertIsNone(variante.precio)
            self.assertNotEqual(variante.precio, Decimal("0"))
            self.assertTrue(variante.activa)
            self.assertTrue(variante.es_predeterminada)

    def test_la_segunda_ejecucion_no_duplica(self):
        importar_catalogo(dry_run=False)
        importar_catalogo(dry_run=False)
        self.assertEqual(Categoria.objects.count(), 7)
        self.assertEqual(Producto.objects.count(), 26)
        self.assertEqual(VarianteProducto.objects.count(), 26)

    def test_un_error_durante_la_carga_revierte_todo(self):
        real = crear_producto_con_variante_inicial
        llamadas = {"n": 0}

        def falla(**kwargs):
            llamadas["n"] += 1
            if llamadas["n"] == 3:
                raise RuntimeError("fallo de prueba")
            return real(**kwargs)

        with patch("apps.catalogo.importacion.crear_producto_con_variante_inicial", side_effect=falla):
            with self.assertRaises(RuntimeError):
                importar_catalogo(dry_run=False)
        self.assertEqual(Categoria.objects.count(), 0)
        self.assertEqual(Producto.objects.count(), 0)
        self.assertEqual(VarianteProducto.objects.count(), 0)

    def test_datos_previos_incompatibles_detienen_la_carga(self):
        Categoria.objects.create(nombre="Otro nombre", slug="alfajores", orden=1)
        with self.assertRaises(ErrorImportacion):
            importar_catalogo(dry_run=True)
        with self.assertRaises(ErrorImportacion):
            importar_catalogo(dry_run=False)
        self.assertEqual(Categoria.objects.count(), 1)
        self.assertEqual(Producto.objects.count(), 0)

    def test_comando_dry_run_no_escribe(self):
        call_command("importar_catalogo_fotografias", "--dry-run")
        self.assertEqual(Producto.objects.count(), 0)
        self.assertEqual(Categoria.objects.count(), 0)

    def test_comando_informa_el_conflicto(self):
        Categoria.objects.create(nombre="Otro nombre", slug="alfajores", orden=1)
        with self.assertRaises(CommandError):
            call_command("importar_catalogo_fotografias", "--dry-run")
