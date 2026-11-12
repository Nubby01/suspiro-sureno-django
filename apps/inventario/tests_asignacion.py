from django.test import Client, TestCase
from django.urls import reverse
from apps.cuentas.models import Usuario
from apps.pedidos.models import Pedido
from . import tests as inventario_tests

class AsignacionTests(TestCase):
    setUp = inventario_tests.InventarioProduccionTests.setUp
    _pedido = inventario_tests.InventarioProduccionTests._pedido

    def test_asignacion_filtra_y_protege_get_post(self):
        propio = self._pedido()
        ajeno = self._pedido()
        propio.responsable = self.ayudante
        propio.save()
        self.client.force_login(self.ayudante)
        for ruta in ("trabajo_asignado", "produccion_trabajo"):
            pagina = self.client.get(reverse(ruta))
            self.assertContains(pagina, propio.codigo)
            self.assertNotContains(pagina, ajeno.codigo)
        url = reverse("produccion_trabajo_detalle", args=[ajeno.codigo])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, {"estado": "listo"}).status_code, 404)
        ajeno.refresh_from_db()
        self.assertEqual(ajeno.estado, Pedido.Estado.RECIBIDO)
        url = reverse("produccion_trabajo_detalle", args=[propio.codigo])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.post(url, {"accion": "asignar", "responsable": ""}).status_code, 403)
        propio.refresh_from_db()
        self.assertEqual(propio.responsable, self.ayudante)

    def test_administracion_asigna_reasigna_y_valida(self):
        pedido = self._pedido()
        url = reverse("produccion_gestion_detalle", args=[pedido.codigo])
        self.client.force_login(self.administradora)
        self.assertContains(self.client.get(url), "Guardar asignación")
        for invalido in (self.clienta.pk, self.administradora.pk, "abc", 999999):
            self.client.post(url, {"accion": "asignar", "responsable": invalido})
            pedido.refresh_from_db()
            self.assertIsNone(pedido.responsable)
        self.client.post(url, {"accion": "asignar", "responsable": self.ayudante.pk})
        pedido.refresh_from_db()
        self.assertEqual(pedido.responsable, self.ayudante)
        self.assertEqual(pedido.eventos.get().usuario, self.administradora)
        self.assertIn("Asignación:", pedido.eventos.get().nota)
        self.ayudante.is_active = False
        self.ayudante.save()
        self.client.post(url, {"accion": "asignar", "responsable": ""})
        self.client.post(url, {"accion": "asignar", "responsable": self.ayudante.pk})
        pedido.refresh_from_db()
        self.assertIsNone(pedido.responsable)

    def test_acceso_y_csrf(self):
        pedido = self._pedido()
        url = reverse("produccion_gestion_detalle", args=[pedido.codigo])
        protegido = Client(enforce_csrf_checks=True)
        protegido.force_login(self.administradora)
        self.assertEqual(protegido.post(url, {"accion": "asignar", "responsable": self.ayudante.pk}).status_code, 403)
        self.client.force_login(self.clienta)
        self.assertEqual(self.client.get(reverse("trabajo_asignado")).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("trabajo_asignado")).status_code, 302)

    def test_navegacion_vacia_y_gestionar(self):
        self.client.force_login(self.clienta)
        for ruta in ("mis_cotizaciones", "mis_pedidos"):
            pagina = self.client.get(reverse(ruta))
            self.assertContains(pagina, 'href="' + reverse("catalogo") + '"')
            self.assertContains(pagina, 'href="' + reverse("mi_cuenta") + '"')
        pedido = self._pedido()
        self.client.force_login(self.administradora)
        pagina = self.client.get(reverse("produccion_gestion"))
        self.assertContains(pagina, 'aria-label="Gestionar pedido ' + pedido.codigo + '"')
        self.assertContains(pagina, reverse("produccion_gestion_detalle", args=[pedido.codigo]))
