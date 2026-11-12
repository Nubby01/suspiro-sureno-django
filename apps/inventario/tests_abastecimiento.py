from datetime import date
from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.urls import reverse
from apps.cuentas.models import Usuario
from .models import Insumo, MovimientoInventario, Abastecimiento, SalidaLote
from .servicios import registrar_movimiento, guardar_insumo
from .formularios import EntradaForm, InsumoForm

class AbastecimientoTests(TestCase):
    def setUp(self):
        self.admin=Usuario.objects.create(username="admin-lotes",rol="administradora")
        self.insumo=guardar_insumo(insumo=Insumo(),nombre="Harina QA",unidad="kg",stock_minimo="5",stock_critico="2",activo=True)

    def entrada(self,clave,cantidad="5",**datos):
        return registrar_movimiento(insumo=self.insumo,tipo="entrada",cantidad=cantidad,motivo="Abastecimiento de prueba",usuario=self.admin,clave=clave,abastecimiento=datos)[0]

    def ajuste(self,clave,cantidad):
        return registrar_movimiento(insumo=self.insumo,tipo="ajuste",cantidad=cantidad,motivo="Ajuste de prueba",usuario=self.admin,clave=clave)

    def test_fefo_preserva_total_y_reintento_no_duplica(self):
        self.ajuste("anterior","10")
        tarde=self.entrada("tarde",caducidad=date(2030,12,1)).abastecimiento
        pronto=self.entrada("pronto",caducidad=date(2030,1,1)).abastecimiento
        salida,creado=self.ajuste("salida","-3")
        pronto.refresh_from_db();tarde.refresh_from_db();self.insumo.refresh_from_db()
        self.assertEqual(pronto.saldo,Decimal("2"));self.assertEqual(tarde.saldo,Decimal("5"))
        self.assertEqual(self.insumo.existencia,Decimal("17"))
        self.assertEqual(SalidaLote.objects.get().abastecimiento,pronto)
        _,creado=self.ajuste("salida","-3")
        self.assertFalse(creado);self.assertEqual(SalidaLote.objects.count(),1)
        self.assertEqual(Abastecimiento.objects.count(),2)

    def test_sin_fecha_despues_de_con_fecha_y_sin_lote_no_se_inventa(self):
        self.ajuste("legado","4")
        sinfecha=self.entrada("sinfecha","2").abastecimiento
        fechado=self.entrada("fechado","1",caducidad=date(2030,1,1)).abastecimiento
        self.ajuste("sale","-5")
        sinfecha.refresh_from_db();fechado.refresh_from_db();self.insumo.refresh_from_db()
        self.assertEqual(sinfecha.saldo,0);self.assertEqual(fechado.saldo,0)
        self.assertEqual(self.insumo.existencia,2)
        self.assertEqual(SalidaLote.objects.count(),2)

    def test_compra_invalida_revierte_entrada_y_saldos(self):
        with self.assertRaises(ValidationError):self.entrada("invalida",precio_compra=100,es_compra=False)
        self.insumo.refresh_from_db()
        self.assertEqual(self.insumo.existencia,0)
        self.assertFalse(MovimientoInventario.objects.exists())
        self.assertFalse(Abastecimiento.objects.exists())
        movimiento=self.entrada("valida",es_compra=True,fecha_compra=date(2026,1,1),precio_compra=100,proveedor="Proveedor QA",tipo_referencia="interna",referencia_compra="COMPRA-QA")
        self.assertTrue(movimiento.abastecimiento.es_compra)
        self.assertIsNone(movimiento.abastecimiento.caducidad)

    def test_falta_stock_no_cambia_lotes(self):
        lote=self.entrada("stock").abastecimiento
        with self.assertRaises(ValidationError):self.ajuste("falla","-6")
        lote.refresh_from_db();self.assertEqual(lote.saldo,5)
        self.assertFalse(SalidaLote.objects.exists())

    def test_stock_configurable_agotado_critico_bajo_normal(self):
        for cantidad,estado in [(0,"agotado"),(1,"critico"),(2,"critico"),(3,"bajo"),(5,"bajo"),(6,"normal")]:
            self.insumo.existencia=Decimal(cantidad);self.assertEqual(self.insumo.nivel_stock,estado)
        self.insumo.stock_critico=None;self.insumo.existencia=1
        self.assertEqual(self.insumo.nivel_stock,"bajo")
        f=InsumoForm({"nombre":"QA","unidad":"kg","stock_minimo":"5","stock_critico":"6","activo":"on"})
        self.assertFalse(f.is_valid());self.assertIn("stock_critico",f.errors)

    def test_historial_y_permisos_y_entrada_no_es_compra(self):
        movimiento=self.entrada("historial")
        self.assertFalse(movimiento.abastecimiento.es_compra)
        self.client.force_login(self.admin)
        respuesta=self.client.get(reverse("inventario_ficha",args=[self.insumo.pk]))
        self.assertContains(respuesta,"compra no identificada")
        self.assertContains(respuesta,"Sin caducidades conocidas")
        for rol in ["ayudante","cliente"]:
            u=Usuario.objects.create(username=rol,rol=rol);self.client.force_login(u)
            self.assertEqual(self.client.get(reverse("inventario_ficha",args=[self.insumo.pk])).status_code,403)

    def test_formulario_no_acepta_datos_de_compra_sin_marca(self):
        f=EntradaForm({"insumo":self.insumo.pk,"cantidad":"1","motivo":"Entrada","clave":"test","fecha_compra":"2026-01-01"})
        self.assertFalse(f.is_valid());self.assertIn("es_compra",f.errors)
