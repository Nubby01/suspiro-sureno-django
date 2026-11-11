from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from apps.cuentas.models import Usuario
from apps.inventario.models import Insumo


class NotificacionesStockTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_user("admin_alertas", rol=Usuario.Rol.ADMINISTRADORA)
        self.ayudante = Usuario.objects.create_user("ayuda_alertas", rol=Usuario.Rol.AYUDANTE)
        self.clienta = Usuario.objects.create_user("cliente_alertas", rol=Usuario.Rol.CLIENTE)
        for nombre, existencia, critico, activo in [
            ("Agotado alerta", 0, None, True),
            ("DEMO · Insumo de prueba", 0, None, True),
            ("Critico alerta", 2, 2, True),
            ("Solo bajo alerta", 4, 2, True),
            ("Normal alerta", 10, 2, True),
            ("Inactivo alerta", 0, 2, False),
        ]:
            Insumo.objects.create(nombre=nombre, unidad="g", existencia=existencia,
                stock_minimo=5, stock_critico=critico, activo=activo)

    def test_admin_recibe_solo_agotados_y_criticos_y_enlaces(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("gestion"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual({x.nombre for x in response.context["alertas_inventario"]},
                         {"Agotado alerta", "Critico alerta"})
        self.assertContains(response, 'aria-label="Alertas de inventario: 2"')
        self.assertContains(response, "Sin stock")
        self.assertContains(response, 'ui-boton--aviso" type="submit">Cerrar sesión')
        for x in response.context["alertas_inventario"]:
            self.assertContains(response, reverse("inventario_ficha", args=[x.pk]))

    def test_sin_alertas(self):
        Insumo.objects.update(existencia=20)
        self.client.force_login(self.admin)
        response = self.client.get(reverse("gestion"))
        self.assertContains(response, "No hay insumos sin stock ni en nivel crítico.")
        self.assertContains(response, 'class="panel-notificaciones__contador" aria-hidden="true" hidden')

    def test_otros_roles_no_reciben_alertas(self):
        self.client.force_login(self.ayudante)
        response = self.client.get(reverse("trabajo"))
        self.assertIsNone(response.context["alertas_inventario"])
        self.assertNotContains(response, 'class="panel-notificaciones"')
        self.client.force_login(self.clienta)
        self.assertEqual(self.client.get(reverse("gestion")).status_code, 403)

    def test_alerta_desaparece_al_reponer_y_reaparece_al_consumir(self):
        self.client.force_login(self.admin)
        url = reverse("alertas_stock")
        self.assertEqual(self.client.get(url).json()["cantidad"], 2)
        Insumo.objects.filter(nombre="Critico alerta").update(existencia=3)
        response = self.client.get(url)
        self.assertEqual(response.json()["cantidad"], 1)
        self.assertNotIn("Critico alerta", response.json()["html"])
        self.assertEqual(response["Cache-Control"], "no-store, private")
        Insumo.objects.filter(nombre="Agotado alerta").update(existencia=10)
        self.assertEqual(self.client.get(url).json()["cantidad"], 0)
        Insumo.objects.filter(nombre="Critico alerta").update(existencia=2)
        self.assertEqual(self.client.get(url).json()["cantidad"], 1)

    def test_endpoint_restringido_y_campana_antes_de_salir(self):
        for usuario in (self.ayudante, self.clienta):
            self.client.force_login(usuario)
            self.assertEqual(self.client.get(reverse("alertas_stock")).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("alertas_stock")).status_code, 302)
        self.client.force_login(self.admin)
        html = self.client.get(reverse("gestion")).content.decode()
        self.assertLess(html.index('class="panel-notificaciones"'), html.index('class="panel-salir"'))
        self.assertIn('class="panel-notificaciones__aviso"', html)
