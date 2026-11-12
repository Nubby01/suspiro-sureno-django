from datetime import datetime, time, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.pedidos.models import EventoPedido, Pedido
from apps.panel.dashboard import dashboard_gestion
from . import tests as base
from .formularios import EntradaForm
from .models import Abastecimiento, Insumo, MovimientoInventario
from .servicios import registrar_movimiento


class MejorasComprasTests(TestCase):
    setUp = base.InventarioProduccionTests.setUp
    _pedido = base.InventarioProduccionTests._pedido
    _insumo = base.InventarioProduccionTests._insumo

    def datos(self, referencia="QA-001", **extra):
        return {"es_compra":True,"fecha_compra":timezone.localdate(),"precio_compra":Decimal("1500"),
                "proveedor":"Proveedor QA","tipo_referencia":"documento","referencia_compra":referencia,**extra}

    def entrada(self, insumo, clave, datos):
        return registrar_movimiento(insumo=insumo,tipo="entrada",cantidad="5",motivo="Compra QA",
            usuario=self.administradora,clave=clave,abastecimiento=datos)

    def test_documento_duplicado_y_reintento_no_ingresan_stock_otra_vez(self):
        insumo=self._insumo()
        self.entrada(insumo,"primera",self.datos())
        _,creado=self.entrada(insumo,"primera",self.datos())
        self.assertFalse(creado)
        with self.assertRaises(ValidationError):
            self.entrada(insumo,"otra-clave",self.datos(" qa-001 ",proveedor=" proveedor   qa "))
        insumo.refresh_from_db()
        self.assertEqual(insumo.existencia,5)
        self.assertEqual(MovimientoInventario.objects.count(),1)
        self.assertEqual(Abastecimiento.objects.count(),1)
        otro=self._insumo(nombre="Azúcar")
        self.entrada(otro,"otro-insumo",self.datos())
        self.assertEqual(Abastecimiento.objects.count(),2)

    def test_compra_interna_y_obligatorios_con_rollback(self):
        insumo=self._insumo()
        for campo in ("fecha_compra","precio_compra","proveedor","referencia_compra","tipo_referencia"):
            datos=self.datos()
            datos[campo]=None if campo in ("fecha_compra","precio_compra") else ""
            with self.assertRaises(ValidationError):
                self.entrada(insumo,"fallo-"+campo,datos)
        self.assertFalse(MovimientoInventario.objects.exists())
        insumo.refresh_from_db();self.assertEqual(insumo.existencia,0)
        self.entrada(insumo,"interna",self.datos("Compra feria 11nov",tipo_referencia="interna"))
        self.assertEqual(Abastecimiento.objects.get().tipo_referencia,"interna")

    def test_legacy_sin_datos_sigue_consultable_y_entrada_no_compra_admitida(self):
        insumo=self._insumo()
        movimiento,_=self.entrada(insumo,"entrada-simple",{})
        registro=movimiento.abastecimiento
        # Simula el estado compatible de una compra antigua, no un alta nueva.
        Abastecimiento.objects.filter(pk=registro.pk).update(es_compra=True)
        self.client.force_login(self.administradora)
        pagina=self.client.get(reverse("inventario_ficha",args=[insumo.pk]))
        self.assertContains(pagina,"No registrada (histórico)")
        self.assertContains(pagina,"Fecha no registrada")
        self.assertEqual(Abastecimiento.objects.get().saldo,5)

    def test_formulario_y_permisos_de_entrada(self):
        insumo=self._insumo()
        datos={"insumo":insumo.pk,"cantidad":"1","motivo":"Compra","clave":"QA","es_compra":"on"}
        formulario=EntradaForm(datos)
        self.assertFalse(formulario.is_valid())
        for campo in ("fecha_compra","precio_compra","proveedor","tipo_referencia","referencia_compra"):
            self.assertIn(campo,formulario.errors)
        for usuario in (self.ayudante,self.clienta):
            self.client.force_login(usuario)
            self.assertEqual(self.client.post(reverse("inventario_entrada"),datos).status_code,403)
        self.client.force_login(self.administradora)
        self.client.get(reverse("inventario_entrada"))
        datos.update(self.datos(tipo_referencia="interna"),clave=self.client.session["clave_entrada"])
        self.assertEqual(self.client.post(reverse("inventario_entrada"),datos).status_code,302)
        self.client.post(reverse("inventario_entrada"),datos)
        insumo.refresh_from_db();self.assertEqual(insumo.existencia,1)
        self.assertEqual(Abastecimiento.objects.count(),1)

    def test_ranking_primera_transicion_listo_cajas_y_ventas_independientes(self):
        pedido=self._pedido(cantidad=3)
        self.variante.nombre="Caja de 4";self.variante.save()
        pedido.lineas.update(nombre_variante="Caja de 4")
        EventoPedido.objects.create(pedido=pedido,estado_anterior="en_preparacion",estado_nuevo="listo")
        EventoPedido.objects.create(pedido=pedido,estado_anterior="listo",estado_nuevo="listo",nota="Reasignación")
        EventoPedido.objects.create(pedido=pedido,estado_anterior="listo",estado_nuevo="entregado")
        datos=dashboard_gestion()
        self.assertEqual(datos["preparados"][0]["unidades"],3)
        self.assertEqual(datos["preparados"][0]["nombre_variante"],"Caja de 4")
        self.assertEqual(datos["ventas"],0)
        antiguo=self._pedido(cantidad=50)
        evento=EventoPedido.objects.create(pedido=antiguo,estado_anterior="en_preparacion",estado_nuevo="listo")
        EventoPedido.objects.filter(pk=evento.pk).update(creada=timezone.now()-timedelta(days=40))
        EventoPedido.objects.create(pedido=antiguo,estado_anterior="en_preparacion",estado_nuevo="listo")
        demo=self._pedido(cantidad=80)
        demo.cotizacion.observaciones="DEMO · preparación";demo.cotizacion.save()
        EventoPedido.objects.create(pedido=demo,estado_anterior="en_preparacion",estado_nuevo="listo")
        self.assertEqual(dashboard_gestion()["preparados"][0]["unidades"],3)

    def test_reporte_fechas_pedido_insumo_precision_y_solo_consumos(self):
        insumo=self._insumo()
        pedido=self._pedido()
        entrada,_=self.entrada(insumo,"stock",{})
        consumo,_=registrar_movimiento(insumo=insumo,tipo="consumo",cantidad="0.125",motivo="Producción QA",
            usuario=self.administradora,clave="consumo-QA",pedido=pedido,consumo=True)
        ayer=timezone.localdate()-timedelta(days=1)
        fecha=timezone.make_aware(datetime.combine(ayer,time(23,59,59)))
        MovimientoInventario.objects.filter(pk=consumo.pk).update(creada=fecha)
        self.client.force_login(self.administradora)
        filtros={"fecha_inicial":ayer.isoformat(),"fecha_final":ayer.isoformat(),"pedido":pedido.pk,"insumo":insumo.pk}
        pagina=self.client.get(reverse("inventario_consumos"),filtros)
        self.assertEqual(pagina.context["resumen_consumos"][0]["consumido"],Decimal("0.125"))
        self.assertEqual([m.pk for m in pagina.context["pagina"]],[consumo.pk])
        self.assertEqual(pagina.context["pagina"][0].cantidad_utilizada,Decimal("0.125"))
        self.assertContains(pagina,reverse("pedido_gestion",args=[pedido.codigo]))
        filtros["fecha_final"]=(ayer-timedelta(days=1)).isoformat()
        pagina=self.client.get(reverse("inventario_consumos"),filtros)
        self.assertTrue(pagina.context["formulario"].errors)
        self.assertEqual(pagina.context["pagina"].paginator.count,0)
        self.assertEqual(MovimientoInventario.objects.get(pk=consumo.pk).creada,fecha)

    def test_reporte_permisos_y_unidades_separadas(self):
        for usuario in (self.ayudante,self.clienta):
            self.client.force_login(usuario)
            self.assertEqual(self.client.get(reverse("inventario_consumos")).status_code,403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("inventario_consumos")).status_code,302)
        self.client.force_login(self.administradora)
        self.assertEqual(self.client.get(reverse("inventario_consumos"),{"fecha_inicial":"fecha-imposible"}).status_code,200)
        pedido=self._pedido()
        harina=self._insumo(nombre="Harina gramos")
        leche=Insumo.objects.create(nombre="Leche litros",unidad="l")
        for insumo,clave in ((harina,"harina"),(leche,"leche")):
            self.entrada(insumo,"entrada-"+clave,{})
            registrar_movimiento(insumo=insumo,tipo="consumo",cantidad="1.125",motivo="Producción QA",
                usuario=self.administradora,clave="salida-"+clave,pedido=pedido,consumo=True)
        pagina=self.client.get(reverse("inventario_consumos"))
        self.assertEqual({fila["insumo__unidad"]:fila["consumido"] for fila in pagina.context["resumen_consumos"]},
                         {"g":Decimal("1.125"),"l":Decimal("1.125")})
        pedido.cotizacion.observaciones="DEMO · consumo";pedido.cotizacion.save()
        self.assertEqual(self.client.get(reverse("inventario_consumos")).context["pagina"].paginator.count,0)
        self.assertEqual(self.client.get(reverse("inventario_consumos"),{"incluir_demo":"on"}).context["pagina"].paginator.count,2)

    def test_alertas_se_actualizan_tras_entradas_y_ajustes_reales(self):
        insumo=self._insumo(minimo="5")
        insumo.stock_critico=2;insumo.save()
        self.client.force_login(self.administradora)
        alerta=reverse("alertas_stock")
        self.assertEqual(self.client.get(alerta).json()["cantidad"],1)
        self.entrada(insumo,"alertas-entrada",{})
        self.assertEqual(self.client.get(alerta).json()["cantidad"],0)
        for delta,esperado,clave in (("-3",1,"critico"),("2",0,"bajo"),("-4",1,"agotado")):
            registrar_movimiento(insumo=insumo,tipo="ajuste",cantidad=delta,motivo="Ajuste QA",
                usuario=self.administradora,clave=clave)
            self.assertEqual(self.client.get(alerta).json()["cantidad"],esperado)
