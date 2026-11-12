from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.cuentas.models import Usuario
from apps.inventario import tests as base
from apps.pedidos.models import EventoPedido, Pedido
from .dashboard import dashboard_gestion, dashboard_trabajo
from apps.pedidos.servicios import registrar_venta
from apps.pedidos.models import VentaPedido


class DashboardTests(TestCase):
    setUp = base.InventarioProduccionTests.setUp
    _pedido = base.InventarioProduccionTests._pedido

    def entrega(self, pedido, hace=1):
        pedido.estado = Pedido.Estado.ENTREGADO
        pedido.save(update_fields=["estado"])
        evento = EventoPedido.objects.create(pedido=pedido, estado_anterior=Pedido.Estado.LISTO,
            estado_nuevo=Pedido.Estado.ENTREGADO, usuario=self.administradora)
        EventoPedido.objects.filter(pk=evento.pk).update(creada=timezone.now() - timedelta(days=hace))
        registrar_venta(pedido=pedido, usuario=self.administradora)

    def test_periodo_entrega_unidades_y_exclusion_demo(self):
        actual = self._pedido(cantidad=3)
        antiguo = self._pedido(cantidad=8)
        demo = self._pedido(cantidad=20)
        demo.cotizacion.observaciones = "DEMO · Pedido de ejemplo"
        demo.cotizacion.save()
        self.entrega(actual)
        self.entrega(antiguo, hace=40)
        self.entrega(demo)
        # Una reasignación histórica no es otra entrega ni duplica unidades.
        EventoPedido.objects.create(pedido=actual, estado_anterior="entregado", estado_nuevo="entregado")
        EventoPedido.objects.create(pedido=antiguo, estado_anterior="entregado", estado_nuevo="entregado")
        datos = dashboard_gestion()
        self.assertEqual(datos["ventas"], 1)
        self.assertEqual(datos["cotizaciones"], 2)
        self.assertEqual(datos["productos"][0]["unidades"], 3)
        self.assertEqual(datos["productos"][0]["porcentaje"], 100)
        # La fecha de creación del pedido no determina su fecha de entrega.
        Pedido.objects.filter(pk=actual.pk).update(creada=timezone.now() - timedelta(days=70))
        self.assertEqual(dashboard_gestion()["ventas"], 1)

    def test_solo_datos_asignados_y_sin_informacion_comercial(self):
        propio = self._pedido()
        propio.responsable = self.ayudante
        propio.save()
        ajeno = self._pedido()
        ajeno.responsable = self.administradora
        ajeno.save()
        demo = self._pedido()
        demo.responsable = self.ayudante
        demo.save()
        demo.cotizacion.observaciones = "Ejemplo de prueba dashboard"
        demo.cotizacion.save()
        datos = dashboard_trabajo(self.ayudante)
        self.assertEqual(datos["asignados"], 1)
        self.assertEqual([p.pk for p in datos["pedidos"]], [propio.pk])
        self.client.force_login(self.ayudante)
        pagina = self.client.get(reverse("trabajo"))
        self.assertContains(pagina, propio.codigo)
        self.assertNotContains(pagina, ajeno.codigo)
        self.assertNotContains(pagina, demo.codigo)
        self.assertNotContains(pagina, "Ingresos")
        self.assertNotContains(pagina, "Estadísticas comerciales")
        self.assertEqual(self.client.get(reverse("gestion")).status_code, 403)

    def test_vacios_y_sin_fingir_visitas_o_cobros(self):
        self.client.force_login(self.administradora)
        pagina = self.client.get(reverse("gestion"))
        self.assertContains(pagina, "Estadísticas comerciales")
        self.assertContains(pagina, "Aún no hay ventas en este período")
        self.assertContains(pagina, "Productos más preparados")
        self.assertNotContains(pagina, "Medición de visitas no configurada")
        self.assertContains(pagina, "Total cobrado de las ventas del período")
        self.assertContains(pagina, "dashboard.css")
        self.client.force_login(self.ayudante)
        self.assertContains(self.client.get(reverse("trabajo")), "Todo al día por aquí")
        self.client.force_login(self.clienta)
        self.assertEqual(self.client.get(reverse("trabajo")).status_code, 403)

    def test_cerrados_no_son_pendientes_y_revocacion(self):
        pedido = self._pedido()
        pedido.responsable = self.ayudante
        pedido.save()
        self.entrega(pedido)
        datos = dashboard_trabajo(self.ayudante)
        self.assertEqual(datos["entregados"], 1)
        self.assertEqual(datos["asignados"], 0)
        self.assertEqual(datos["pedidos"], [])
        pedido.responsable = None
        pedido.save()
        self.assertEqual(dashboard_trabajo(self.ayudante)["entregados"], 0)
