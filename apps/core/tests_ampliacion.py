from django.test import TestCase
from django.urls import reverse
from django.contrib.messages import get_messages
from apps.cuentas.models import Usuario
from apps.catalogo.models import Categoria,Producto,VarianteProducto
from apps.inventario.models import Insumo

class AmpliacionTests(TestCase):
    def setUp(self):
        self.admin=Usuario.objects.create(username="admin-qa",rol="administradora")
        cat=Categoria.objects.create(nombre="QA",slug="qa")
        producto=Producto.objects.create(nombre="Producto QA",slug="producto-qa",categoria=cat)
        self.variante=VarianteProducto.objects.create(producto=producto,precio=1000)

    def test_contador_persiste_actualiza_y_se_vacia_al_quitar(self):
        r=self.client.post(reverse("cotizacion_agregar"),{"variante":self.variante.pk,"cantidad":2},follow=True)
        self.assertContains(r,"2 presentaciones seleccionadas")
        self.assertContains(r,"El producto quedó en la cotización")
        r=self.client.post(reverse("cotizaciones"),{"accion":"actualizar","indice":0,"cantidad":3},follow=True)
        self.assertContains(r,"3 presentaciones seleccionadas");self.assertContains(r,"Cantidad actualizada")
        r=self.client.post(reverse("cotizaciones"),{"accion":"actualizar","indice":0,"quitar":"1"},follow=True)
        self.assertNotContains(r,'class="cotizacion-contador"');self.assertContains(r,"Ver cotización");self.assertContains(r,"Producto eliminado")

    def test_demo_oculto_se_puede_mostrar_y_no_se_borra(self):
        real=Insumo.objects.create(nombre="Harina real",unidad="kg")
        demo=Insumo.objects.create(nombre="DEMO · Harina QA",unidad="kg")
        self.client.force_login(self.admin)
        r=self.client.get(reverse("inventario_gestion"))
        self.assertContains(r,real.nombre);self.assertNotContains(r,demo.nombre)
        r=self.client.get(reverse("inventario_gestion"),{"incluir_demo":"1"})
        self.assertContains(r,demo.nombre);self.assertEqual(Insumo.objects.count(),2)

    def test_login_logout_avisos_por_rol(self):
        for rol in ["administradora","ayudante","cliente"]:
            user=Usuario.objects.create_user(username="qa-"+rol,password="Prueba-local-9876",rol=rol)
            r=self.client.post(reverse("ingresar"),{"username":user.username,"password":"Prueba-local-9876"},follow=True)
            self.assertContains(r,"Iniciaste sesión correctamente")
            r=self.client.post(reverse("salir"),follow=True)
            self.assertContains(r,"Cerraste sesión correctamente")
        r=self.client.post(reverse("ingresar"),{"username":"no-existe","password":"invalida"})
        self.assertContains(r,"No pudimos iniciar sesión")
