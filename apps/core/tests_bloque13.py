from django.test import TestCase
from django.urls import reverse
from apps.catalogo.models import Categoria, Producto, VarianteProducto
from apps.cotizaciones.models import Cotizacion, LineaCotizacion
from apps.cotizaciones.pdf import construir_cotizacion
from apps.cuentas.models import Usuario
from apps.pedidos.models import Pedido


class Bloque13Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = Usuario.objects.create(username="admin-qa", rol=Usuario.Rol.ADMINISTRADORA)
        cls.ayuda = Usuario.objects.create(username="ayuda-qa", rol=Usuario.Rol.AYUDANTE)
        cls.clienta = Usuario.objects.create(username="cliente-qa", email="cliente@example.com", rol=Usuario.Rol.CLIENTE)
        cls.categoria = Categoria.objects.create(nombre="Categoría de prueba", slug="categoria-prueba")
        cls.producto = Producto.objects.create(categoria=cls.categoria, nombre="Producto de prueba", slug="producto-prueba", referencia_imagen="imagenes/catalogo-web/alfajormanjarcatalogo.jpg")
        cls.variante = VarianteProducto.objects.create(producto=cls.producto, nombre="Presentación de prueba", precio=3500)
        cls.cotizacion = Cotizacion.objects.create(nombre="Cliente de prueba", correo="cliente@example.com", telefono="+56900000000", cliente=cls.clienta)
        LineaCotizacion.objects.create(cotizacion=cls.cotizacion, variante=cls.variante, nombre_producto=cls.producto.nombre, cantidad=2, precio_acordado=3500)
        cls.pedido = Pedido.objects.create(cotizacion=cls.cotizacion, responsable=cls.ayuda, nombre=cls.cotizacion.nombre, correo=cls.cotizacion.correo, telefono=cls.cotizacion.telefono, total=7000)

    def test_seccion_activa_en_detalles_y_permisos_se_conservan(self):
        rutas = [("cotizacion_gestion", [self.cotizacion.codigo], "cotizaciones_gestion"),
                 ("pedido_gestion", [self.pedido.codigo], "pedidos_gestion"),
                 ("produccion_gestion_detalle", [self.pedido.codigo], "produccion_gestion"),
                 ("cliente_detalle", [self.clienta.pk], "clientes_gestion"),
                 ("catalogo_editar", [self.producto.pk], "catalogo_interno")]
        self.client.force_login(self.admin)
        for nombre,args,seccion in rutas:
            with self.subTest(nombre=nombre):
                respuesta = self.client.get(reverse(nombre,args=args))
                self.assertEqual(respuesta.status_code,200)
                self.assertContains(respuesta, 'href="'+reverse(seccion)+'" aria-current="page"')
        self.client.force_login(self.ayuda)
        self.assertEqual(self.client.get(reverse("cotizacion_gestion",args=[self.cotizacion.codigo])).status_code,403)
        respuesta=self.client.get(reverse("produccion_trabajo_detalle",args=[self.pedido.codigo]))
        self.assertContains(respuesta, 'href="'+reverse("produccion_trabajo")+'" aria-current="page"')
        self.client.force_login(self.clienta)
        self.assertEqual(self.client.get(reverse("gestion")).status_code,403)

    def test_portada_usa_categoria_real_y_no_escribe_catalogo(self):
        antes=list(VarianteProducto.objects.values())
        respuesta=self.client.get(reverse("inicio"))
        self.assertContains(respuesta,'#categoria-categoria-prueba')
        self.assertContains(respuesta,self.categoria.nombre)
        self.assertEqual(antes,list(VarianteProducto.objects.values()))

    def test_pdf_total_privacidad_y_varias_paginas(self):
        pdf=construir_cotizacion(self.cotizacion)
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertIn(b"$7.000",pdf)
        self.assertNotIn(self.cotizacion.token.encode(),pdf)
        self.assertIn(b"/Subtype /Image",pdf)
        LineaCotizacion.objects.bulk_create([LineaCotizacion(cotizacion=self.cotizacion,variante=self.variante,nombre_producto="Producto largo con detalle "*4,detalle="Detalle de prueba "*8,cantidad=1,precio_acordado=None) for _ in range(45)])
        pdf=construir_cotizacion(self.cotizacion)
        self.assertIn(b"Total pendiente",pdf)
        self.assertGreater(pdf.count(b"/Type /Page\n"),1)
        self.assertNotIn(self.cotizacion.token.encode(),pdf)
