from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.catalogo.importacion import MANIFIESTO, importar_catalogo
from apps.catalogo.models import Categoria, Producto, VarianteProducto
from apps.catalogo.imagenes import ruta_fisica
from apps.catalogo.rollitos import (
    PORTADA_DEFINITIVA,
    PORTADA_PROVISIONAL,
    SABORES,
    SLUG,
    ErrorRollitos,
    cargar_rollitos,
)
from apps.cuentas.models import Usuario

CLAVE = "una-clave-segura-19"


def _huella_productos(excluir=""):
    consulta = Producto.objects.all()
    if excluir:
        consulta = consulta.exclude(slug=excluir)
    return list(
        consulta.order_by("id").values_list(
            "id", "nombre", "slug", "referencia_imagen", "activo", "categoria_id"
        )
    )


def _huella_variantes(excluir=""):
    consulta = VarianteProducto.objects.all()
    if excluir:
        consulta = consulta.exclude(producto__slug=excluir)
    return list(
        consulta.order_by("id").values_list(
            "id", "producto__slug", "nombre", "precio", "es_predeterminada", "activa"
        )
    )


class RollitosSaboresTests(TestCase):
    def setUp(self):
        importar_catalogo()

    def test_la_carga_es_idempotente_y_conserva_los_originales(self):
        self.assertEqual(len(MANIFIESTO), 26)
        self.assertNotIn(SLUG, [item["slug"] for item in MANIFIESTO])
        productos = _huella_productos()
        variantes = _huella_variantes()
        self.assertEqual(len(productos), 26)
        resultado = cargar_rollitos()
        self.assertTrue(resultado["creado"])
        self.assertEqual(Producto.objects.count(), 27)
        self.assertEqual(VarianteProducto.objects.count(), 27)
        self.assertEqual(Categoria.objects.count(), 7)
        nuevo = Producto.objects.get(slug=SLUG)
        variante = nuevo.variantes.get()
        self.assertEqual(nuevo.nombre, "Rollitos de sabores")
        self.assertEqual(nuevo.categoria.slug, "rollos-dulces")
        self.assertTrue(nuevo.activo)
        portada_esperada = (
            PORTADA_DEFINITIVA if ruta_fisica(PORTADA_DEFINITIVA) else PORTADA_PROVISIONAL
        )
        self.assertEqual(nuevo.referencia_imagen, portada_esperada)
        self.assertEqual(resultado["provisional"], portada_esperada != PORTADA_DEFINITIVA)
        self.assertIsNone(variante.precio)
        self.assertEqual(variante.nombre, "")
        self.assertTrue(variante.es_predeterminada)
        self.assertEqual(_huella_productos(SLUG), productos)
        self.assertEqual(_huella_variantes(SLUG), variantes)
        sabores = list(
            nuevo.galeria.order_by("orden").values_list(
                "producto_origen__slug", "orden", "referencia_imagen", "nombre"
            )
        )
        self.assertEqual([fila[0] for fila in sabores], list(SABORES))
        self.assertEqual([fila[1] for fila in sabores], list(range(1, 8)))
        self.assertTrue(all(fila[2] == "" and fila[3] == "" for fila in sabores))
        repetido = cargar_rollitos()
        self.assertFalse(repetido["creado"])
        self.assertEqual(Producto.objects.count(), 27)
        self.assertEqual(nuevo.galeria.count(), 7)
        self.assertEqual(_huella_productos(SLUG), productos)

    def test_sin_un_sabor_no_crea_el_producto(self):
        oreo = Producto.objects.get(slug="rollo-oreo")
        oreo.slug = "rollo-oreo-apartado"
        oreo.save(update_fields=["slug"])
        with self.assertRaises(ErrorRollitos):
            cargar_rollitos()
        self.assertFalse(Producto.objects.filter(slug=SLUG).exists())
        self.assertEqual(Producto.objects.count(), 26)

    def test_la_portada_definitiva_reemplaza_solo_la_provisional(self):
        cargar_rollitos()
        canela = Producto.objects.get(slug="rollo-de-canela")
        foto_canela = canela.referencia_imagen

        def ruta(valor):
            if valor == PORTADA_DEFINITIVA:
                return Path("presente")
            from apps.catalogo.imagenes import ruta_fisica

            return ruta_fisica(valor)

        with patch("apps.catalogo.rollitos.ruta_fisica", side_effect=ruta):
            resultado = cargar_rollitos()
        nuevo = Producto.objects.get(slug=SLUG)
        canela.refresh_from_db()
        self.assertFalse(resultado["provisional"])
        self.assertEqual(nuevo.referencia_imagen, PORTADA_DEFINITIVA)
        self.assertEqual(canela.referencia_imagen, foto_canela)
        self.assertIsNone(nuevo.variantes.get().precio)

    def test_catalogo_publico_detalle_y_carrusel(self):
        cargar_rollitos()
        listado = self.client.get(reverse("catalogo"))
        self.assertContains(listado, "Rollitos de sabores")
        self.assertContains(listado, "Consultar precio")
        for slug in SABORES:
            self.assertContains(listado, Producto.objects.get(slug=slug).nombre)
        self.assertEqual(listado.content.decode().count("Ver sabores"), 1)
        self.assertContains(listado, 'href="/catalogo/rollitos-de-sabores/"')
        detalle = self.client.get(reverse("producto_detalle", kwargs={"slug": SLUG}))
        self.assertContains(detalle, "Consultar precio")
        if ruta_fisica(PORTADA_DEFINITIVA):
            self.assertContains(detalle, PORTADA_DEFINITIVA)
        self.assertNotContains(detalle, "$8.500")
        self.assertNotContains(detalle, "$10.500")
        self.assertNotContains(detalle, "data-precio")
        self.assertContains(detalle, "Sabor anterior")
        self.assertContains(detalle, "Sabor siguiente")
        self.assertContains(detalle, 'type="button"')
        self.assertContains(detalle, "sabores.js")
        self.assertContains(detalle, 'tabindex="0"')
        self.assertNotContains(detalle, "autoplay")
        for slug in SABORES:
            self.assertContains(detalle, Producto.objects.get(slug=slug).nombre)
            self.assertContains(detalle, Producto.objects.get(slug=slug).referencia_imagen)
        rollo = self.client.get(reverse("producto_detalle", kwargs={"slug": "rollo-de-canela"}))
        self.assertContains(rollo, "Rollo de canela")
        self.assertNotContains(rollo, "data-sabores")
        javascript = (settings.BASE_DIR / "static" / "js" / "sabores.js").read_text(encoding="utf-8")
        css = (settings.BASE_DIR / "static" / "css" / "catalogo.css").read_text(encoding="utf-8")
        self.assertNotIn("setInterval", javascript)
        self.assertNotIn("setTimeout", javascript)
        self.assertNotIn("autoplay", javascript)
        self.assertIn("ArrowLeft", javascript)
        self.assertIn("pointerup", javascript)
        self.assertIn("prefers-reduced-motion: reduce", css)
        self.assertIn("minmax(0, 1fr)", css)
        self.assertIn("overflow-wrap: anywhere", css)

    def test_el_panel_muestra_el_producto_sin_precio(self):
        cargar_rollitos()
        administradora = Usuario.objects.create_user(
            "administra",
            "administra@example.com",
            CLAVE,
            rol=Usuario.Rol.ADMINISTRADORA,
        )
        self.client.force_login(administradora)
        pagina = self.client.get(reverse("catalogo_interno"))
        self.assertContains(pagina, "Rollitos de sabores")
        self.assertContains(pagina, "Consultar precio")
        self.assertNotContains(pagina, "$0")


@override_settings(PERMITIR_CUENTAS_DEMOSTRACION=True)
class CuentasDemostracionTests(TestCase):
    def test_crea_los_tres_roles_sin_privilegios_ni_borrados(self):
        ajena = Usuario.objects.create_user(
            "admin",
            "",
            CLAVE,
            rol=Usuario.Rol.ADMINISTRADORA,
            is_staff=True,
            is_superuser=True,
        )
        clave_inicial = ajena.password
        respuestas = [CLAVE, CLAVE] * 3
        with patch(
            "apps.cuentas.management.commands.crear_cuentas_demostracion.getpass.getpass",
            side_effect=respuestas,
        ):
            call_command("crear_cuentas_demostracion")
        self.assertEqual(Usuario.objects.count(), 4)
        ajena.refresh_from_db()
        self.assertEqual(ajena.password, clave_inicial)
        self.assertTrue(ajena.is_superuser)
        esperados = {
            "demo-administradora": Usuario.Rol.ADMINISTRADORA,
            "demo-ayudante": Usuario.Rol.AYUDANTE,
            "demo-clienta": Usuario.Rol.CLIENTE,
        }
        for username, rol in esperados.items():
            usuario = Usuario.objects.get(username=username)
            self.assertEqual(usuario.rol, rol)
            self.assertFalse(usuario.is_staff)
            self.assertFalse(usuario.is_superuser)
            self.assertTrue(usuario.is_active)
            self.assertTrue(usuario.check_password(CLAVE))
            self.assertNotEqual(usuario.password, CLAVE)
            self.assertTrue(usuario.password.startswith("pbkdf2_"))
        with patch(
            "apps.cuentas.management.commands.crear_cuentas_demostracion.getpass.getpass",
            side_effect=AssertionError("no debe pedir otra contraseña"),
        ):
            call_command("crear_cuentas_demostracion")
        self.assertEqual(Usuario.objects.count(), 4)
        fuente = Path(
            settings.BASE_DIR
            / "apps/cuentas/management/commands/crear_cuentas_demostracion.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn(".delete(", fuente)
        self.assertNotIn(CLAVE, fuente)

    def test_los_tres_roles_entran_donde_corresponde(self):
        respuestas = [CLAVE, CLAVE] * 3
        with patch(
            "apps.cuentas.management.commands.crear_cuentas_demostracion.getpass.getpass",
            side_effect=respuestas,
        ):
            call_command("crear_cuentas_demostracion")
        self.client.login(username="demo-administradora", password=CLAVE)
        self.assertRedirects(
            self.client.post(reverse("ingresar"), {"username": "demo-administradora", "password": CLAVE}),
            reverse("gestion"),
        )
        self.assertEqual(self.client.get(reverse("gestion")).status_code, 200)
        self.assertEqual(self.client.get("/admin/").status_code, 403)
        self.client.logout()
        ingreso_ayuda = self.client.post(
            reverse("ingresar"),
            {"username": "demo-ayudante", "password": CLAVE},
        )
        self.assertRedirects(ingreso_ayuda, reverse("trabajo"))
        self.assertEqual(self.client.get(reverse("gestion")).status_code, 403)
        self.client.logout()
        ingreso_clienta = self.client.post(
            reverse("ingresar"),
            {"username": "demo-clienta", "password": CLAVE},
        )
        self.assertRedirects(ingreso_clienta, reverse("mi_cuenta"))
        self.assertEqual(self.client.get(reverse("gestion")).status_code, 403)
        self.assertEqual(self.client.get(reverse("trabajo")).status_code, 403)

    def test_no_altera_una_cuenta_de_demostracion_con_privilegios(self):
        Usuario.objects.create_superuser("demo-ayudante", "demo-ayudante@example.com", CLAVE)
        with patch(
            "apps.cuentas.management.commands.crear_cuentas_demostracion.getpass.getpass",
            side_effect=[CLAVE, CLAVE],
        ):
            with self.assertRaises(CommandError):
                call_command("crear_cuentas_demostracion")
        ayudante = Usuario.objects.get(username="demo-ayudante")
        self.assertTrue(ayudante.is_superuser)
        self.assertFalse(Usuario.objects.filter(username="demo-clienta").exists())

    @override_settings(PERMITIR_CUENTAS_DEMOSTRACION=False, DEBUG=False)
    def test_rechaza_otro_entorno_sin_crear_cuentas(self):
        with self.assertRaises(CommandError):
            call_command("crear_cuentas_demostracion")
        self.assertEqual(Usuario.objects.count(), 0)
