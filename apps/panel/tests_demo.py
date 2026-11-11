from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.catalogo.models import Categoria
from apps.catalogo.servicios import crear_producto_con_variante_inicial
from apps.cotizaciones.models import Cotizacion, LineaCotizacion
from apps.cotizaciones.servicios import confirmar
from apps.cuentas.models import Usuario
from apps.inventario.models import Insumo
from apps.pedidos.models import Pedido
from apps.pedidos.servicios import cambiar_estado, convertir
from apps.panel.demo import cargar_demo_negocio

CLAVE = "una-clave-segura-19"


@override_settings(DEBUG=True)
class DemoNegocioTests(TestCase):
    def setUp(self):
        self.clienta = Usuario.objects.create_user(
            "demo-clienta",
            "demo-clienta@example.com",
            CLAVE,
            first_name="Clienta",
            last_name="Demo",
            rol=Usuario.Rol.CLIENTE,
            telefono="+56911111111",
        )
        Usuario.objects.create_user(
            "demo-administradora",
            "demo-administradora@example.com",
            CLAVE,
            rol=Usuario.Rol.ADMINISTRADORA,
        )
        self.administradora = Usuario.objects.get(username="demo-administradora")
        categoria = Categoria.objects.create(nombre="Pies", slug="pies", orden=1)
        self.pie = crear_producto_con_variante_inicial(
            categoria=categoria,
            nombre="Pie de limón",
            slug="pie-de-limon",
            precio=Decimal("13000"),
        )

    def test_la_carga_es_idempotente_y_no_toca_un_pedido_real(self):
        primero = cargar_demo_negocio()
        self.assertEqual(primero["pedidos_nuevos"], 5)
        self.assertEqual(Insumo.objects.filter(nombre__startswith="DEMO · ").count(), 10)
        self.assertEqual(Pedido.objects.count(), 5)
        estados = set(Pedido.objects.values_list("estado", flat=True))
        self.assertEqual(
            estados,
            {
                Pedido.Estado.RECIBIDO,
                Pedido.Estado.EN_PREPARACION,
                Pedido.Estado.LISTO,
                Pedido.Estado.ENTREGADO,
                Pedido.Estado.CANCELADO,
            },
        )
        harina = Insumo.objects.get(nombre="DEMO · Harina")
        self.assertEqual(harina.existencia, Decimal("0"))
        segundo = cargar_demo_negocio()
        self.assertEqual(segundo["pedidos_nuevos"], 0)
        self.assertEqual(Pedido.objects.count(), 5)
        harina.refresh_from_db()
        self.assertEqual(harina.existencia, Decimal("0"))

        otra = Usuario.objects.create_user(
            "real@example.com",
            "real@example.com",
            CLAVE,
            rol=Usuario.Rol.CLIENTE,
            telefono="+56922222222",
        )
        cotizacion = Cotizacion.objects.create(
            cliente=otra,
            nombre="Ana Real",
            correo="real@example.com",
            telefono="+56922222222",
            observaciones="Pedido del taller",
        )
        variante = self.pie.variantes.get()
        LineaCotizacion.objects.create(
            cotizacion=cotizacion,
            variante=variante,
            nombre_producto=self.pie.nombre,
            cantidad=1,
            precio_acordado=variante.precio,
        )
        confirmar(cotizacion=cotizacion)
        pedido = convertir(cotizacion=cotizacion, usuario=self.administradora)
        with self.assertRaises(ValidationError):
            cambiar_estado(
                pedido=pedido,
                estado=Pedido.Estado.EN_PREPARACION,
                usuario=self.administradora,
                nota="Intento real",
            )
        harina.refresh_from_db()
        self.assertEqual(harina.existencia, Decimal("0"))
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.Estado.RECIBIDO)

    def test_el_comando_exige_confirmacion_y_no_corre_sin_debug(self):
        with self.assertRaises(CommandError):
            call_command("cargar_demo_negocio")
        self.assertEqual(Pedido.objects.count(), 0)
        with override_settings(DEBUG=False):
            with self.assertRaises(CommandError):
                call_command("cargar_demo_negocio", "--confirmar")
        self.assertEqual(Pedido.objects.count(), 0)

    def test_la_administradora_lista_clientas_sin_secretos(self):
        self.client.force_login(self.administradora)
        vacio = self.client.get(reverse("clientes_gestion"), {"q": "nadie-en-el-taller"})
        self.assertContains(vacio, "No hay clientas")
        pagina = self.client.get(reverse("clientes_gestion"), {"q": "Clienta", "incluir_demo": "1"})
        self.assertContains(pagina, "demo-clienta@example.com")
        self.assertNotContains(pagina, CLAVE)
        self.assertNotContains(pagina, "password")
        detalle = self.client.get(reverse("cliente_detalle", args=[self.clienta.pk]))
        self.assertContains(detalle, "Clienta Demo")
        self.assertContains(detalle, "Esta clienta todavía no tiene pedidos.")
        self.client.logout()
        self.client.force_login(self.clienta)
        self.assertEqual(self.client.get(reverse("clientes_gestion")).status_code, 403)
