"""Regresión: los textos públicos no pueden activar marcadores internos."""
from types import SimpleNamespace

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.catalogo.models import Categoria, Producto, VarianteProducto
from apps.cuentas.models import Usuario
from apps.inventario.models import Receta
from apps.inventario.servicios import _recetas_de_linea, pedido_es_demostracion
from apps.panel.demostracion import criterio_demo
from apps.pedidos.servicios import convertir

from .models import Cotizacion
from .servicios import confirmar, solicitar


class MarcadoresDemoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        categoria = Categoria.objects.create(nombre="QA", slug="qa-marcador")
        producto = Producto.objects.create(nombre="Producto QA", slug="qa-marcador", categoria=categoria)
        cls.variante = VarianteProducto.objects.create(producto=producto, precio=1000)
        cls.cliente = Usuario.objects.create(username="qa-cliente", rol="cliente")
        cls.admin = Usuario.objects.create(username="qa-admin", rol="administradora")
        cls.demo = Receta.objects.create(producto=producto, variante=cls.variante, alcance=f"ejemplo:v{cls.variante.pk}", rendimiento=1)

    def datos(self, **extra):
        datos = dict(cliente=self.cliente, nombre="Cliente QA", correo="qa@example.invalid",
                     telefono="+56911111111", observaciones="Entrega normal",
                     lineas=[dict(variante_id=self.variante.pk, cantidad=1)])
        datos.update(extra)
        return datos

    def test_servicio_rechaza_prefijos_para_cualquier_sesion_sin_escrituras(self):
        for usuario in (self.cliente, AnonymousUser(), self.admin):
            for campo in ("nombre", "observaciones"):
                for texto in ("DEMO · ataque", "  demo · ataque  ", "DeMo · ataque", "Ejemplo de prueba falso", "EJEMPLO DE PRUEBA falso"):
                    with self.subTest(usuario=str(usuario), campo=campo, texto=texto):
                        with self.assertRaisesMessage(ValidationError, "reservado"):
                            solicitar(**self.datos(cliente=usuario, **{campo: texto}))
                        self.assertEqual(Cotizacion.objects.count(), 0)

    def test_post_publico_manipulado_no_crea_cotizacion_ni_pedido(self):
        from apps.pedidos.models import Pedido
        for usuario in (None, self.cliente):
            if usuario:
                self.client.force_login(usuario)
            self.client.post(reverse("cotizacion_agregar"), {"variante": self.variante.pk, "cantidad": 1})
            respuesta = self.client.post(reverse("cotizaciones"), {
                "nombre": "Cliente QA", "correo": "qa@example.invalid", "telefono": "+56911111111",
                "observaciones": "DEMO · ataque", "es_demo": "1", "rol": "administradora",
            })
            self.assertContains(respuesta, "reservado")
            self.assertEqual(Cotizacion.objects.count(), 0)
            self.assertEqual(Pedido.objects.count(), 0)

    def test_texto_ordinario_no_activa_demo_recetas_ni_exclusion(self):
        cotizacion = solicitar(**self.datos(observaciones="Quiero comentar DEMO · y Ejemplo de prueba como texto normal"))
        confirmar(cotizacion=cotizacion)
        pedido = convertir(cotizacion=cotizacion, usuario=self.admin)
        self.assertFalse(pedido_es_demostracion(pedido))
        self.assertTrue(Cotizacion.objects.exclude(criterio_demo("observaciones")).filter(pk=cotizacion.pk).exists())
        self.assertFalse(_recetas_de_linea(pedido.lineas.first()).filter(pk=self.demo.pk).exists())
        from apps.panel.dashboard import dashboard_gestion
        self.assertEqual(dashboard_gestion()["ventas"], 1)

    def test_demo_interno_e_historicos_conservan_clasificacion(self):
        for texto in ("DEMO · interno autorizado", "Ejemplo de prueba histórico"):
            cotizacion = Cotizacion.objects.create(nombre="QA", correo="qa@example.invalid", telefono="+56911111111", observaciones=texto)
            antes = cotizacion.observaciones
            self.assertTrue(Cotizacion.objects.filter(criterio_demo("observaciones"), pk=cotizacion.pk).exists())
            cotizacion.refresh_from_db()
            self.assertEqual(cotizacion.observaciones, antes)
        pedido = SimpleNamespace(cotizacion=Cotizacion.objects.get(observaciones="DEMO · interno autorizado"))
        self.assertTrue(pedido_es_demostracion(pedido))
        linea = SimpleNamespace(pedido=pedido, variante=self.variante)
        self.assertTrue(_recetas_de_linea(linea).filter(pk=self.demo.pk).exists())
