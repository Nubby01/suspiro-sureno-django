from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse

from apps.catalogo.models import Categoria, Producto, VarianteProducto
from apps.catalogo.precios_comerciales import aplicar_propuestas
from apps.catalogo.cajas import aplicar_cajas_faltantes
from apps.catalogo.precios_confirmados import aplicar_precios_confirmados
from apps.catalogo.servicios import crear_producto_con_variante_inicial
from apps.cuentas.models import Usuario
from apps.inventario.models import Insumo

CLAVE = "una-clave-segura-19"


class PreciosComercialesTests(TestCase):
    def setUp(self):
        self.categoria = Categoria.objects.create(nombre="Pies", slug="pies", orden=1)

    def _producto(self, nombre, slug, precio=None, mayorista=None, nombre_variante=""):
        return crear_producto_con_variante_inicial(
            categoria=self.categoria,
            nombre=nombre,
            slug=slug,
            precio=precio,
            precio_mayorista=mayorista,
            nombre_variante=nombre_variante,
        )

    def test_el_mayorista_negativo_no_se_guarda(self):
        producto = self._producto("Pie de limón", "pie-de-limon")
        variante = producto.variantes.get()
        variante.precio_mayorista = Decimal("-1")
        with self.assertRaises(ValidationError):
            variante.full_clean()

    def test_la_vista_previa_no_escribe_y_la_carga_es_idempotente(self):
        pie = self._producto("Pie de limón", "pie-de-limon")
        caja = self._producto("Rollitos de sabores", "rollitos-de-sabores")
        otro = self._producto("Rollo de canela", "rollo-de-canela")
        antes = Producto.objects.count()

        call_command("revisar_precios_comerciales")
        pie.variantes.get().refresh_from_db()
        self.assertIsNone(pie.variantes.get().precio)

        aplicar_propuestas()
        aplicar_propuestas()
        pie.variantes.get().refresh_from_db()
        caja.variantes.get().refresh_from_db()
        otro.variantes.get().refresh_from_db()
        self.assertEqual(pie.variantes.get().precio, Decimal("13000"))
        self.assertIsNone(pie.variantes.get().precio_mayorista)
        self.assertEqual(caja.variantes.get().precio, Decimal("10500"))
        self.assertIsNone(otro.variantes.get().precio)
        self.assertEqual(Producto.objects.count(), antes)
        self.assertEqual(VarianteProducto.objects.count(), antes)

        pie.variantes.update(precio=Decimal("5000"))
        aplicar_propuestas()
        self.assertEqual(pie.variantes.get().precio, Decimal("5000"))

    def test_el_catalogo_publico_oculta_el_mayorista(self):
        producto = self._producto("Pie reservado", "pie-reservado", precio=Decimal("4500"), mayorista=Decimal("2100"))
        respuesta = self.client.get(reverse("catalogo"))
        html = respuesta.content.decode()
        self.assertContains(respuesta, "$4.500")
        self.assertContains(respuesta, "<dialog")
        self.assertContains(respuesta, "Agregar a la cotización")
        self.assertContains(respuesta, "Cerrar")
        self.assertContains(respuesta, 'aria-labelledby="selector-titulo-%s"' % producto.pk)
        self.assertNotContains(respuesta, "2.100")
        self.assertNotContains(respuesta, "2100")
        self.assertNotIn("precio_mayorista", html)
        self.assertNotIn("Precio mayorista", html)

    def test_visitante_clienta_y_ayudante_no_ven_el_mayorista(self):
        producto = self._producto("Pie reservado", "pie-reservado", precio=Decimal("4500"), mayorista=Decimal("864219"))
        clienta = Usuario.objects.create_user("ana", "ana@example.com", CLAVE, rol=Usuario.Rol.CLIENTE)
        ayudante = Usuario.objects.create_user("ayuda", "ayuda@example.com", CLAVE, rol=Usuario.Rol.AYUDANTE)
        administradora = Usuario.objects.create_user(
            "administra",
            "administra@example.com",
            CLAVE,
            rol=Usuario.Rol.ADMINISTRADORA,
        )
        for pagina in (reverse("catalogo"), reverse("cotizaciones")):
            anonima = self.client.get(pagina)
            self.assertNotContains(anonima, "864219")
        self.assertEqual(self.client.get(reverse("mi_cuenta")).status_code, 302)
        self.client.force_login(clienta)
        for pagina in (reverse("catalogo"), reverse("mi_cuenta"), reverse("cotizaciones")):
            self.assertNotContains(self.client.get(pagina), "864219")
        self.client.force_login(ayudante)
        self.assertNotContains(self.client.get(reverse("trabajo")), "864219")
        self.assertEqual(self.client.get(reverse("catalogo_variantes", args=[producto.pk])).status_code, 403)
        self.client.force_login(administradora)
        panel = self.client.get(reverse("catalogo_variantes", args=[producto.pk]))
        self.assertContains(panel, "Precio mayorista")
        self.assertContains(panel, "864219")

    def test_el_navegador_no_cambia_el_precio_de_catalogo(self):
        producto = self._producto("Pie reservado", "pie-reservado", precio=Decimal("4500"), mayorista=Decimal("2100"))
        variante = producto.variantes.get()
        self.client.post(
            reverse("cotizacion_agregar"),
            {
                "variante": variante.pk,
                "cantidad": "2",
                "precio": "1",
                "subtotal": "1",
                "precio_mayorista": "2100",
                "origen": "/catalogo/",
            },
        )
        pagina = self.client.get(reverse("cotizaciones"))
        self.assertContains(pagina, "$4.500")
        self.assertNotContains(pagina, "2.100")
        self.assertNotContains(pagina, "2100")
        variante.refresh_from_db()
        self.assertEqual(variante.precio, Decimal("4500"))
        self.assertEqual(variante.precio_mayorista, Decimal("2100"))

    def test_django_admin_muestra_el_mayorista_solo_a_la_superusuaria(self):
        self._producto("Pie reservado", "pie-reservado", precio=Decimal("4500"), mayorista=Decimal("864219"))
        Usuario = get_user_model()
        superusuaria = Usuario.objects.create_superuser("root", "root@example.com", CLAVE)
        self.client.force_login(superusuaria)
        respuesta = self.client.get(reverse("admin:catalogo_varianteproducto_changelist"))
        self.assertContains(respuesta, "$864.219")
        self.assertContains(respuesta, "Precio mayorista")


class PreciosConfirmadosTests(TestCase):
    def setUp(self):
        self.categoria = Categoria.objects.create(nombre="Pies", slug="pies", orden=1)

    def _producto(self, nombre, slug, precio=None, mayorista=None, nombre_variante=""):
        return crear_producto_con_variante_inicial(
            categoria=self.categoria,
            nombre=nombre,
            slug=slug,
            precio=precio,
            precio_mayorista=mayorista,
            nombre_variante=nombre_variante,
        )

    def test_carga_precios_variantes_y_no_toca_lo_ajeno(self):
        alfajor = self._producto("Alfajor manjar", "alfajor-manjar", mayorista=Decimal("864219"))
        torta = self._producto("Torta de galleta", "torta-de-galleta")
        canela = self._producto("Rollo de canela", "rollo-de-canela")
        otro = self._producto("Rollo Oreo", "rollo-oreo")
        salado = self._producto("Rollo de ajo", "rollo-de-ajo")
        porcion = self._producto("Porción pie de limón", "porcion-pie-de-limon")
        berlines = self._producto("Berlines", "berlines")
        antes = Producto.objects.count()
        insumos = Insumo.objects.count()

        with self.assertRaises(CommandError):
            call_command("cargar_precios_confirmados")
        self.assertIsNone(alfajor.variantes.get().precio)

        aplicar_precios_confirmados()
        aplicar_precios_confirmados()
        call_command("cargar_precios_confirmados", confirmar=True)

        alfajor.variantes.get().refresh_from_db()
        self.assertEqual(alfajor.variantes.get().precio, Decimal("2000"))
        self.assertEqual(alfajor.variantes.get().precio_mayorista, Decimal("864219"))
        self.assertEqual(canela.variantes.get().nombre, "Caja de 4")
        self.assertEqual(canela.variantes.get().precio, Decimal("8500"))
        self.assertEqual(berlines.variantes.get().precio, Decimal("5000"))
        self.assertIsNone(otro.variantes.get().precio)
        self.assertIsNone(salado.variantes.get().precio)
        self.assertIsNone(porcion.variantes.get().precio)
        self.assertEqual(torta.variantes.filter(activa=True).count(), 5)
        self.assertEqual(torta.variantes.filter(es_predeterminada=True).count(), 1)
        self.assertEqual(torta.variantes.get(es_predeterminada=True).nombre, "10 personas")
        self.assertEqual(torta.variantes.get(nombre="30 personas").precio, Decimal("32000"))
        self.assertEqual(Producto.objects.count(), antes)
        self.assertFalse(Producto.objects.filter(slug="cheesecake-oreo").exists())
        self.assertFalse(Producto.objects.filter(slug="pie-de-frambuesa").exists())
        self.assertEqual(Insumo.objects.count(), insumos)

        pagina = self.client.get(reverse("catalogo"))
        self.assertContains(pagina, "$2.000")
        self.assertContains(pagina, "Cantidad de personas")
        self.assertContains(pagina, '<span class="variante-opcion"><span>30 personas</span><strong>$32.000</strong></span>', html=True)
        self.assertContains(pagina, "Caja de 4")
        self.assertContains(pagina, "Pastelera")
        self.assertContains(pagina, "data-precio=\"32000\"")
        self.assertNotContains(pagina, "864219")
        self.assertNotContains(pagina, "Precio mayorista")

    def test_no_pisa_una_presentacion_distinta(self):
        self._producto("Alfajor manjar", "alfajor-manjar", precio=Decimal("1500"), nombre_variante="Docena")
        aplicar_precios_confirmados()
        variante = VarianteProducto.objects.get()
        self.assertEqual(variante.nombre, "Docena")
        self.assertEqual(variante.precio, Decimal("1500"))

    def test_las_cajas_de_un_sabor_no_pisan_precios_existentes(self):
        canela = self._producto(
            "Rollo de canela",
            "rollo-de-canela",
            precio=Decimal("8500"),
            nombre_variante="Caja de 4",
        )
        oreo = self._producto("Rollo Oreo", "rollo-oreo")
        ajo = self._producto("Rollo de ajo", "rollo-de-ajo")
        aplicar_cajas_faltantes()
        aplicar_cajas_faltantes()
        canela.variantes.get().refresh_from_db()
        oreo.variantes.get().refresh_from_db()
        ajo.variantes.get().refresh_from_db()
        self.assertEqual(canela.variantes.get().precio, Decimal("8500"))
        self.assertEqual(oreo.variantes.get().precio, Decimal("9000"))
        self.assertEqual(oreo.variantes.get().nombre, "Caja de 4")
        self.assertEqual(ajo.variantes.get().precio, Decimal("10500"))
        self.assertEqual(Producto.objects.count(), 3)
        self.assertEqual(oreo.variantes.count(), 1)
