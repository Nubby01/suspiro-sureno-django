from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from .formularios import EntradaForm
from .models import Insumo


class FechasEntradaTests(TestCase):
    def setUp(self):
        self.insumo = Insumo.objects.create(nombre="Azúcar fechas", unidad="g")
        self.hoy = timezone.localdate()

    def formulario(self, **fechas):
        return EntradaForm({"insumo":self.insumo.pk,"cantidad":"10","motivo":"Ingreso histórico", "clave":"fecha-qa", "es_compra":"on", "proveedor":"Proveedor QA", "precio_compra":"100", "tipo_referencia":"interna", "referencia_compra":"COMPRA-FECHAS", **fechas})

    def test_fecha_obligatoria_para_compra(self):
        self.assertFalse(self.formulario().is_valid())
        self.assertIn("fecha_compra",self.formulario().errors)

    def test_compra_futura_rechazada(self):
        form = self.formulario(fecha_compra=(self.hoy+timedelta(days=1)).isoformat())
        self.assertFalse(form.is_valid())
        self.assertIn("fecha_compra",form.errors)
        self.assertEqual(form.fields["fecha_compra"].widget.attrs["max"],self.hoy.isoformat())

    def test_caducidad_anterior_rechazada(self):
        form=self.formulario(fecha_compra=self.hoy.isoformat(),caducidad=(self.hoy-timedelta(days=1)).isoformat())
        self.assertFalse(form.is_valid())
        self.assertIn("caducidad",form.errors)

    def test_historial_y_mismo_dia_permitidos(self):
        for caducidad in (self.hoy-timedelta(days=10),self.hoy-timedelta(days=30)):
            form=self.formulario(fecha_compra=(self.hoy-timedelta(days=30)).isoformat(),caducidad=caducidad.isoformat())
            self.assertTrue(form.is_valid(),form.errors)

    def test_fecha_imposible(self):
        form=self.formulario(fecha_compra="2026-02-30")
        self.assertFalse(form.is_valid())
        self.assertIn("fecha_compra",form.errors)
