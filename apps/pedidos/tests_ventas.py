from datetime import timedelta
from decimal import Decimal
from importlib import import_module
from types import SimpleNamespace

from django.apps import apps
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.inventario import tests as base
from apps.inventario.models import ConsumoPedido, MovimientoInventario, Insumo
from apps.inventario.servicios import agregar_ingrediente
from apps.panel.dashboard import dashboard_gestion
from .models import EventoPedido, Pedido, VentaPedido, LineaPedido
from .servicios import registrar_venta, cambiar_estado, convertir
from apps.cotizaciones.models import Cotizacion, LineaCotizacion
from apps.cotizaciones.servicios import confirmar


class VentasStockTests(TestCase):
    setUp = base.InventarioProduccionTests.setUp
    _pedido = base.InventarioProduccionTests._pedido
    _insumo = base.InventarioProduccionTests._insumo
    _entrada = base.InventarioProduccionTests._entrada
    _receta = base.InventarioProduccionTests._receta

    def test_conversion_a_recibido_registra_cobro_sin_descontar_stock(self):
        insumo = self._insumo()
        self._entrada(insumo, "100")
        cotizacion = Cotizacion.objects.create(nombre="Prueba comercial", correo="prueba@example.com", telefono="+56911112222")
        LineaCotizacion.objects.create(cotizacion=cotizacion, variante=self.variante,
            nombre_producto=self.producto.nombre, cantidad=2, precio_acordado=Decimal("1500"))
        confirmar(cotizacion=cotizacion)
        pedido = convertir(cotizacion=cotizacion, usuario=self.administradora)
        self.assertEqual(pedido.estado, "recibido")
        self.assertEqual(pedido.venta.total, 3000)
        self.assertFalse(pedido.venta.fecha_estimada)
        self.assertEqual(pedido.venta.usuario, self.administradora)
        self.assertEqual(dashboard_gestion()["ingresos"], "$3.000")
        insumo.refresh_from_db()
        self.assertEqual(insumo.existencia, 100)
        self.assertFalse(ConsumoPedido.objects.exists())
        with self.assertRaises(ValidationError):
            convertir(cotizacion=cotizacion, usuario=self.administradora)
        self.assertEqual(VentaPedido.objects.count(), 1)

    def test_recibido_es_venta_y_avanzar_no_duplica_ni_recobra(self):
        self.insumo = self._insumo()
        self._entrada(self.insumo, "100")
        self._receta(cantidad="10")
        pedido = self._pedido(cantidad=2)
        registrar_venta(pedido=pedido, usuario=self.administradora)
        venta = VentaPedido.objects.get(pedido=pedido)
        for estado in ("en_preparacion", "listo", "entregado"):
            cambiar_estado(pedido=pedido, estado=estado, usuario=self.administradora)
            self.assertEqual(VentaPedido.objects.filter(pedido=pedido).count(), 1)
            self.assertEqual(VentaPedido.objects.get(pedido=pedido).fecha, venta.fecha)
            self.assertEqual(dashboard_gestion()["ventas"], 1)
        self.insumo.refresh_from_db()
        self.assertEqual(self.insumo.existencia, Decimal("80"))
        self.assertEqual(ConsumoPedido.objects.filter(pedido=pedido).count(), 1)
        self.assertEqual(MovimientoInventario.objects.filter(pedido=pedido, tipo="consumo").count(), 1)
        self.assertEqual(dashboard_gestion()["ingresos"], "$1.000")
        self.assertEqual(dashboard_gestion()["productos"][0]["unidades"], 2)

    def test_no_cuenta_dos_veces_en_otro_periodo_y_cancelar_no_es_reembolso(self):
        pedido = self._pedido()
        venta = registrar_venta(pedido=pedido, usuario=self.administradora)
        VentaPedido.objects.filter(pk=venta.pk).update(fecha=timezone.now() - timedelta(days=40))
        cambiar_estado(pedido=pedido, estado="cancelado", usuario=self.administradora, nota="Cancelación sin devolución registrada")
        self.assertTrue(VentaPedido.objects.filter(pedido=pedido).exists())
        self.assertEqual(dashboard_gestion()["ventas"], 0)
        self.assertEqual(dashboard_gestion()["ingresos"], "$0")

    def test_migracion_historial_y_fallback_sin_alterar_stock(self):
        recibido = self._pedido()
        entregado = self._pedido()
        entregado.estado = "entregado"
        entregado.save()
        evento = EventoPedido.objects.create(pedido=entregado, estado_anterior="", estado_nuevo="recibido", usuario=self.administradora)
        fecha = timezone.now() - timedelta(days=40)
        EventoPedido.objects.filter(pk=evento.pk).update(creada=fecha)
        EventoPedido.objects.create(pedido=entregado, estado_anterior="listo", estado_nuevo="entregado")
        migration = import_module("apps.pedidos.migrations.0004_reconocer_ventas_existentes")
        migration.reconocer_ventas(apps, SimpleNamespace(connection=SimpleNamespace(alias="default")))
        migration.reconocer_ventas(apps, SimpleNamespace(connection=SimpleNamespace(alias="default")))
        self.assertEqual(VentaPedido.objects.count(), 2)
        self.assertTrue(VentaPedido.objects.get(pedido=recibido).fecha_estimada)
        self.assertEqual(VentaPedido.objects.get(pedido=entregado).fecha, fecha)
        self.assertFalse(MovimientoInventario.objects.exists())
        self.assertEqual(dashboard_gestion()["ventas"], 1)

    def test_falta_receta_o_stock_revierte_todo_el_pedido(self):
        self.insumo = self._insumo()
        self._entrada(self.insumo, "100")
        self._receta(cantidad="10")
        pedido = self._pedido(cantidad=2)
        otro = self._insumo(nombre="Cacao")
        self._entrada(otro, "1", clave="cacao")
        agregar_ingrediente(producto=self.producto, variante=None, insumo=otro,
            cantidad="5", rendimiento="1", unidad="g")
        with self.assertRaises(ValidationError):
            cambiar_estado(pedido=pedido, estado="en_preparacion", usuario=self.administradora)
        pedido.refresh_from_db(); self.insumo.refresh_from_db(); otro.refresh_from_db()
        self.assertEqual(pedido.estado, "recibido")
        self.assertEqual(self.insumo.existencia, 100)
        self.assertEqual(otro.existencia, 1)
        self.assertFalse(ConsumoPedido.objects.exists())
        self.assertFalse(MovimientoInventario.objects.filter(tipo="consumo").exists())

    def test_boton_ventas_y_marca_en_listado_y_detalle(self):
        pedido = self._pedido()
        registrar_venta(pedido=pedido, usuario=self.administradora)
        self.client.force_login(self.administradora)
        self.assertContains(self.client.get(reverse("pedido_gestion", args=[pedido.codigo])), "Venta realizada")
        self.assertContains(self.client.get(reverse("pedidos_gestion"), {"ventas":"1", "periodo":"30"}), pedido.codigo)
        self.client.force_login(self.ayudante)
        self.assertEqual(self.client.get(reverse("pedidos_gestion"), {"ventas":"1"}).status_code, 403)

    def test_ingreso_inmutable_y_demostraciones_excluidas(self):
        pedido = self._pedido()
        registrar_venta(pedido=pedido, usuario=self.administradora)
        Pedido.objects.filter(pk=pedido.pk).update(total=9000)
        pedido.refresh_from_db()
        registrar_venta(pedido=pedido, usuario=self.administradora)
        demo = self._pedido()
        demo.cotizacion.observaciones = "DEMO · Venta de ejemplo"
        demo.cotizacion.save()
        registrar_venta(pedido=demo, usuario=self.administradora)
        self.assertEqual(dashboard_gestion()["ventas"], 1)
        self.assertEqual(dashboard_gestion()["ingresos"], "$1.000")

    def test_stock_de_todas_las_lineas_y_rendimiento_desde_la_pantalla(self):
        self.insumo = self._insumo()
        self._entrada(self.insumo, "100")
        self._receta(cantidad="10", rendimiento="2")
        pedido = self._pedido(cantidad=2)
        LineaPedido.objects.create(pedido=pedido, variante=self.variante,
            nombre_producto=self.producto.nombre, cantidad=3, precio_acordado=1000)
        pedido.responsable = self.ayudante
        pedido.save()
        self.client.force_login(self.ayudante)
        url = reverse("produccion_trabajo_detalle", args=[pedido.codigo])
        self.client.post(url, {"estado":"en_preparacion"})
        self.insumo.refresh_from_db()
        self.assertEqual(self.insumo.existencia, 75)  # (2 + 3) × 10 / 2
        self.client.post(url, {"estado":"en_preparacion"})
        self.insumo.refresh_from_db()
        self.assertEqual(self.insumo.existencia, 75)
        self.assertEqual(MovimientoInventario.objects.filter(pedido=pedido,tipo="consumo").get().cantidad, -25)
