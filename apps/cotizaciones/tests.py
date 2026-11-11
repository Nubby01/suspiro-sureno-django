from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from apps.catalogo.models import Categoria, Producto, VarianteProducto
from apps.inventario.models import Insumo
from apps.inventario.servicios import agregar_ingrediente, registrar_movimiento
from apps.catalogo.servicios import crear_producto_con_variante_inicial
from apps.cotizaciones.models import Cotizacion
from apps.cotizaciones.servicios import confirmar, fijar_precios
from apps.cuentas.models import Usuario
from apps.pedidos.models import Pedido
from apps.pedidos.servicios import cambiar_estado, convertir

CLAVE = "una-clave-segura-19"


class CotizacionesPedidosTests(TestCase):
    def setUp(self):
        self.categoria = Categoria.objects.create(nombre="Alfajores", slug="alfajores", orden=1)
        self.producto = crear_producto_con_variante_inicial(
            categoria=self.categoria,
            nombre="Alfajor manjar",
            slug="alfajor-manjar",
            precio=None,
        )
        self.otro = crear_producto_con_variante_inicial(
            categoria=self.categoria,
            nombre="Alfajor nuez",
            slug="alfajor-nuez",
            precio=None,
        )
        self.variante = self.producto.variantes.get()
        self.administradora = Usuario.objects.create_user(
            "administra",
            "administra@example.com",
            CLAVE,
            rol=Usuario.Rol.ADMINISTRADORA,
        )
        self.clienta = Usuario.objects.create_user(
            "ana",
            "ana@example.com",
            CLAVE,
            rol=Usuario.Rol.CLIENTE,
            first_name="Ana",
            last_name="Prueba",
        )
        self.otra = Usuario.objects.create_user(
            "luz",
            "luz@example.com",
            CLAVE,
            rol=Usuario.Rol.CLIENTE,
        )
        self.ayudante = Usuario.objects.create_user(
            "ayuda",
            "ayuda@example.com",
            CLAVE,
            rol=Usuario.Rol.AYUDANTE,
        )

    def _agregar(self, variante=None, **extra):
        datos = {
            "variante": str((variante or self.variante).pk),
            "cantidad": "2",
            "origen": "/catalogo/",
            "precio": "8500",
            "cliente": str(self.administradora.pk),
        }
        datos.update(extra)
        return self.client.post(reverse("cotizacion_agregar"), datos)

    def _enviar(self, **extra):
        datos = {
            "nombre": "Ana Visita",
            "correo": "  Ana.Visita@Example.com ",
            "telefono": "9 1111 2222",
            "observaciones": "Sin azúcar extra.",
            "cliente": str(self.administradora.pk),
            "estado": "confirmada",
            "total": "10500",
        }
        datos.update(extra)
        return self.client.post(reverse("cotizaciones"), datos)

    def _habilitar_preparacion(self, pedido):
        insumo = Insumo.objects.create(
            nombre=f"Harina de prueba {pedido.pk}",
            unidad=Insumo.Unidad.GRAMO,
            stock_minimo=Decimal("0"),
        )
        registrar_movimiento(
            insumo=insumo,
            tipo="entrada",
            cantidad=Decimal("1000"),
            motivo="Stock para la prueba de preparación.",
            usuario=self.administradora,
            clave=f"entrada-prueba-{pedido.pk}",
        )
        for linea in pedido.lineas.select_related("variante__producto"):
            agregar_ingrediente(
                producto=linea.variante.producto,
                variante=None,
                insumo=insumo,
                cantidad=Decimal("10"),
                rendimiento=Decimal("1"),
                unidad=Insumo.Unidad.GRAMO,
            )

    def _precios(self, cotizacion, valores):
        datos = {"accion": "precios"}
        for linea in cotizacion.lineas.all():
            datos[f"precio_{linea.pk}"] = valores.get(linea.pk, "")
        return self.client.post(reverse("cotizacion_gestion", args=[cotizacion.codigo]), datos)

    def test_visitante_solicita_sin_precio_ni_identificador_secuencial(self):
        self._agregar()
        pagina = self.client.get(reverse("cotizaciones"))
        self.assertContains(pagina, "Alfajor manjar")
        self.assertContains(pagina, "Consultar precio")
        self.assertNotContains(pagina, "$8.500")
        self.assertNotContains(pagina, "$10.500")
        respuesta = self._enviar()
        cotizacion = Cotizacion.objects.get()
        self.assertRedirects(respuesta, reverse("cotizacion_consulta", args=[cotizacion.token]))
        self.assertIsNone(cotizacion.cliente_id)
        self.assertEqual(cotizacion.correo, "ana.visita@example.com")
        self.assertEqual(cotizacion.telefono, "+56911112222")
        self.assertEqual(cotizacion.estado, Cotizacion.Estado.SOLICITADA)
        self.assertNotEqual(cotizacion.codigo, str(cotizacion.pk))
        self.assertGreater(len(cotizacion.token), 30)
        linea = cotizacion.lineas.get()
        self.assertIsNone(linea.precio_acordado)
        self.assertEqual(linea.cantidad, 2)
        self.assertIsNone(cotizacion.total())
        self.assertIsNone(self.variante.precio)
        self.assertEqual(self.client.get("/cotizacion/1/").status_code, 404)
        self.assertEqual(self.client.get(reverse("cotizacion_consulta", args=["no-existe"])).status_code, 404)
        consulta = self.client.get(reverse("cotizacion_consulta", args=[cotizacion.token]))
        self.assertContains(consulta, cotizacion.codigo)
        self.assertContains(consulta, "Total pendiente")
        pdf = self.client.get(reverse("cotizacion_pdf", args=[cotizacion.token]))
        self.assertEqual(pdf["Content-Type"], "application/pdf")
        self.assertTrue(pdf.content.startswith(b"%PDF"))
        self.assertIn(cotizacion.codigo.encode(), pdf.content)
        from unittest.mock import patch
        with patch("apps.cotizaciones.pdf.CORREO", "contacto@example.com"), patch("apps.cotizaciones.pdf.WHATSAPP_VISIBLE", "+56 9 0000 0000"):
            pdf_contacto = self.client.get(reverse("cotizacion_pdf", args=[cotizacion.token]))
        self.assertIn(b"contacto@example.com", pdf_contacto.content)
        self.assertIn(b"+56 9 0000 0000", pdf_contacto.content)
        self.assertIn(b"/Subtype /Image", pdf.content)
        self.assertNotIn(cotizacion.token.encode(), pdf.content)
        self.assertNotIn("devol".encode(), pdf.content.lower())
        self.assertEqual(self.client.get(reverse("cotizacion_pdf", args=["otro-token"])).status_code, 404)

    def test_clienta_solo_ve_las_suyas_y_el_post_no_cambia_el_rol(self):
        self.client.force_login(self.clienta)
        self._agregar()
        self._enviar(nombre="Ana Prueba", correo="ana@example.com", telefono="+56911112222")
        cotizacion = Cotizacion.objects.get()
        self.assertEqual(cotizacion.cliente, self.clienta)
        self.assertEqual(self.clienta.rol, Usuario.Rol.CLIENTE)
        propias = self.client.get(reverse("mis_cotizaciones"))
        self.assertContains(propias, cotizacion.codigo)
        self.client.force_login(self.otra)
        ajenas = self.client.get(reverse("mis_cotizaciones"))
        self.assertNotContains(ajenas, cotizacion.codigo)
        self.assertEqual(self.client.get(reverse("cotizacion_gestion", args=[cotizacion.codigo])).status_code, 403)
        self.assertEqual(self.client.get(reverse("cotizacion_pdf_gestion", args=[cotizacion.codigo])).status_code, 403)
        self.client.logout()
        anonimo = self.client.get(reverse("mis_cotizaciones"))
        self.assertEqual(anonimo.status_code, 302)
        self.assertIn("/cuenta/ingresar/", anonimo["Location"])

    def test_rechaza_producto_inactivo_cantidad_y_sabores_invalidos(self):
        self.producto.activo = False
        self.producto.save(update_fields=["activo"])
        self._agregar()
        self.assertEqual(Cotizacion.objects.count(), 0)
        self.assertNotIn("cotizacion_borrador", self.client.session)
        self.producto.activo = True
        self.producto.save(update_fields=["activo"])
        self.assertEqual(self._agregar(cantidad="0").status_code, 302)
        self.assertEqual(self._agregar(cantidad="-3").status_code, 302)
        self.assertNotIn("cotizacion_borrador", self.client.session)
        self._agregar(sabor_1="rollo-de-canela")
        self.assertNotIn("cotizacion_borrador", self.client.session)
        caja = crear_producto_con_variante_inicial(
            categoria=self.categoria,
            nombre="Rollitos de sabores",
            slug="rollitos-de-sabores",
            precio=None,
        )
        for slug, nombre in (("rollo-de-canela", "Rollo de canela"), ("rollo-oreo", "Rollo Oreo")):
            crear_producto_con_variante_inicial(
                categoria=self.categoria,
                nombre=nombre,
                slug=slug,
                precio=None,
            )
        self._agregar(variante=caja.variantes.get(), sabor_1="rollo-de-canela", sabor_2="rollo-oreo", cantidad="1")
        self._enviar(nombre="Caja", correo="caja@example.com", telefono="911112222")
        linea = Cotizacion.objects.get().lineas.get()
        self.assertEqual(linea.detalle, "Rollo de canela y Rollo Oreo")
        self.assertIsNone(linea.precio_acordado)
        self.assertFalse(Producto.objects.filter(nombre__icontains="caja mixta").exists())
        self.assertIsNone(caja.variantes.get().precio)

    def test_el_brownie_exige_un_centro_valido_y_no_fija_precio(self):
        self._agregar(sabor_brownie="menta")
        self.assertEqual(Cotizacion.objects.count(), 0)
        brownie = crear_producto_con_variante_inicial(
            categoria=self.categoria,
            nombre="Alfajor brownie con relleno",
            slug="alfajor-brownie-con-relleno",
            precio=None,
        )
        variante = brownie.variantes.get()
        self._agregar(variante=variante, sabor_brownie="pizza")
        self.assertEqual(Cotizacion.objects.count(), 0)
        self._agregar(variante=variante, sabor_brownie="menta", cantidad="1")
        self._enviar(nombre="Brownie", correo="brownie@example.com", telefono="911112222")
        linea = Cotizacion.objects.get().lineas.get()
        self.assertEqual(linea.detalle, "Menta")
        self.assertIsNone(linea.precio_acordado)
        self.assertIsNone(variante.precio)
        self.assertEqual(brownie.variantes.count(), 1)

    def test_confirma_convierte_y_no_duplica_ni_cambia_el_catalogo(self):
        self._agregar(cantidad="2")
        self._agregar(variante=self.otro.variantes.get(), cantidad="1")
        self._enviar()
        cotizacion = Cotizacion.objects.get()
        self.client.force_login(self.administradora)
        self.assertEqual(self.client.get(reverse("cotizaciones_gestion")).status_code, 200)
        lineas = list(cotizacion.lineas.order_by("id"))
        self._precios(cotizacion, {lineas[0].pk: "1500"})
        cotizacion.refresh_from_db()
        self.assertEqual(cotizacion.estado, Cotizacion.Estado.EN_REVISION)
        self.assertIsNone(cotizacion.total())
        with self.assertRaises(ValidationError):
            confirmar(cotizacion=cotizacion)
        self._precios(cotizacion, {lineas[0].pk: "1500", lineas[1].pk: "0"})
        cotizacion.refresh_from_db()
        self.assertEqual(cotizacion.total(), Decimal("3000"))
        self.client.post(reverse("cotizacion_gestion", args=[cotizacion.codigo]), {"accion": "confirmar"})
        cotizacion.refresh_from_db()
        self.assertEqual(cotizacion.estado, Cotizacion.Estado.CONFIRMADA)
        with self.assertRaises(ValidationError):
            confirmar(cotizacion=cotizacion)
        pedido = convertir(cotizacion=cotizacion, usuario=self.administradora)
        with self.assertRaises(ValidationError):
            convertir(cotizacion=cotizacion, usuario=self.administradora)
        self.assertEqual(Pedido.objects.count(), 1)
        self.assertEqual(pedido.total, Decimal("3000"))
        self.assertEqual(pedido.lineas.count(), 2)
        self.assertIsNone(VarianteProducto.objects.get(pk=self.variante.pk).precio)
        self.assertIsNone(self.otro.variantes.get().precio)
        with self.assertRaises(ValidationError):
            cambiar_estado(pedido=pedido, estado="entregado", usuario=self.administradora)
        self._habilitar_preparacion(pedido)
        cambiar_estado(pedido=pedido, estado="en_preparacion", usuario=self.administradora)
        cambiar_estado(pedido=pedido, estado="listo", usuario=self.administradora, nota="Listo en el taller.")
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, "listo")
        self.assertEqual(pedido.eventos.count(), 3)
        self.assertEqual(pedido.eventos.latest("id").usuario, self.administradora)
        self.client.force_login(self.clienta)
        self.assertEqual(self.client.get(reverse("mis_pedidos")).status_code, 200)
        self.assertNotContains(self.client.get(reverse("mis_pedidos")), pedido.codigo)

    def test_rechazo_cancelacion_y_transicion_de_pedido(self):
        self._agregar(cantidad="1")
        self._enviar(nombre="Rechazo", correo="rechazo@example.com")
        cotizacion = Cotizacion.objects.get()
        self.client.force_login(self.administradora)
        vacio = self.client.post(
            reverse("cotizacion_gestion", args=[cotizacion.codigo]),
            {"accion": "rechazar", "motivo": ""},
        )
        self.assertEqual(vacio.status_code, 200)
        cotizacion.refresh_from_db()
        self.assertEqual(cotizacion.estado, Cotizacion.Estado.SOLICITADA)
        self.client.post(
            reverse("cotizacion_gestion", args=[cotizacion.codigo]),
            {"accion": "rechazar", "motivo": "No hay producción esta semana."},
        )
        cotizacion.refresh_from_db()
        self.assertEqual(cotizacion.estado, Cotizacion.Estado.RECHAZADA)
        self.assertIn("producción", cotizacion.motivo)
        with self.assertRaises(ValidationError):
            convertir(cotizacion=cotizacion, usuario=self.administradora)
        self._agregar(cantidad="1")
        self._enviar(nombre="Otra", correo="otra@example.com", telefono="911112223")
        segunda = Cotizacion.objects.get(correo="otra@example.com")
        linea = segunda.lineas.get()
        fijar_precios(cotizacion=segunda, precios={linea.pk: Decimal("2000")})
        confirmar(cotizacion=segunda)
        pedido = convertir(cotizacion=segunda, usuario=self.administradora)
        with self.assertRaises(ValidationError):
            cambiar_estado(pedido=pedido, estado="cancelado", usuario=self.administradora, nota="")
        cambiar_estado(pedido=pedido, estado="cancelado", usuario=self.administradora, nota="La clienta avisó.")
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, "cancelado")
        with self.assertRaises(ValidationError):
            cambiar_estado(pedido=pedido, estado="en_preparacion", usuario=self.administradora)

    def test_permisos_csrf_y_precio_negativo(self):
        self.client.force_login(self.ayudante)
        self.assertEqual(self.client.get(reverse("cotizaciones_gestion")).status_code, 403)
        self.assertEqual(self.client.get(reverse("pedidos_gestion")).status_code, 403)
        self.client.force_login(self.administradora)
        self._agregar(cantidad="1")
        self._enviar(nombre="Precio", correo="precio@example.com")
        cotizacion = Cotizacion.objects.get()
        linea = cotizacion.lineas.get()
        respuesta = self._precios(cotizacion, {linea.pk: "-1"})
        self.assertEqual(respuesta.status_code, 200)
        linea.refresh_from_db()
        self.assertIsNone(linea.precio_acordado)
        cliente = Client(enforce_csrf_checks=True)
        rechazo = cliente.post(
            reverse("cotizacion_agregar"),
            {"variante": str(self.variante.pk), "cantidad": "1", "origen": "/catalogo/"},
        )
        self.assertEqual(rechazo.status_code, 403)
        self.assertEqual(Cotizacion.objects.count(), 1)
        self._agregar(cantidad="1")
        invalido = self._enviar(nombre="Teléfono", correo="telefono@example.com", telefono="123")
        self.assertEqual(invalido.status_code, 200)
        self.assertFalse(Cotizacion.objects.filter(correo="telefono@example.com").exists())

    def test_el_panel_no_crea_dos_pedidos_y_la_clienta_solo_ve_el_suyo(self):
        self.client.force_login(self.clienta)
        self._agregar(cantidad="1")
        self._enviar(nombre="Ana Prueba", correo="ana@example.com", telefono="911112222")
        cotizacion = Cotizacion.objects.get()
        self.client.force_login(self.administradora)
        linea = cotizacion.lineas.get()
        self._precios(cotizacion, {linea.pk: "4500"})
        self.client.post(reverse("cotizacion_gestion", args=[cotizacion.codigo]), {"accion": "confirmar"})
        primera = self.client.post(
            reverse("cotizacion_gestion", args=[cotizacion.codigo]),
            {"accion": "convertir"},
        )
        segunda = self.client.post(
            reverse("cotizacion_gestion", args=[cotizacion.codigo]),
            {"accion": "convertir"},
        )
        self.assertEqual(primera.status_code, 302)
        self.assertEqual(segunda.status_code, 302)
        self.assertEqual(Pedido.objects.count(), 1)
        pedido = Pedido.objects.get()
        self.assertEqual(pedido.cliente, self.clienta)
        self.assertEqual(pedido.total, Decimal("4500"))
        self.assertIsNone(VarianteProducto.objects.get(pk=self.variante.pk).precio)
        self.client.force_login(self.clienta)
        self.assertContains(self.client.get(reverse("mis_pedidos")), pedido.codigo)
        self.client.force_login(self.otra)
        self.assertNotContains(self.client.get(reverse("mis_pedidos")), pedido.codigo)
        self.assertEqual(self.client.get(reverse("pedido_gestion", args=[pedido.codigo])).status_code, 403)

    def test_berlines_guardan_sabores_y_el_precio_del_servidor(self):
        caja = crear_producto_con_variante_inicial(
            categoria=self.categoria,
            nombre="Berlines",
            slug="berlines",
            precio=Decimal("5000"),
            nombre_variante="Caja de 4",
        )
        variante = caja.variantes.get()
        self._agregar(variante=variante, sabor_1="", cantidad="1")
        self._agregar(variante=variante, sabor_1="rollo-de-ajo", cantidad="1")
        self.assertEqual(Cotizacion.objects.count(), 0)
        self._agregar(variante=variante, sabor_1="manjar", sabor_2="chocolate", cantidad="2", precio="1")
        self._enviar(nombre="Caja", correo="berlines@example.com", telefono="911112222")
        linea = Cotizacion.objects.get().lineas.get()
        self.assertEqual(linea.detalle, "Manjar y Chocolate")
        self.assertEqual(linea.nombre_variante, "Caja de 4")
        self.assertEqual(linea.precio_acordado, Decimal("5000"))
        variante.precio = Decimal("9000")
        variante.save(update_fields=["precio"])
        linea.refresh_from_db()
        self.assertEqual(linea.precio_acordado, Decimal("5000"))

    def test_la_torta_conserva_el_precio_de_la_variante_elegida(self):
        from apps.catalogo.precios_confirmados import aplicar_precios_confirmados

        torta = crear_producto_con_variante_inicial(
            categoria=self.categoria,
            nombre="Torta de bizcocho",
            slug="torta-de-bizcocho",
            precio=None,
        )
        aplicar_precios_confirmados()
        grande = torta.variantes.get(nombre="30 personas")
        self._agregar(variante=grande, cantidad="1", precio="24000")
        self._enviar(nombre="Torta", correo="torta@example.com", telefono="911112222")
        cotizacion = Cotizacion.objects.get()
        linea = cotizacion.lineas.get()
        self.assertEqual(linea.nombre_variante, "30 personas")
        self.assertEqual(linea.precio_acordado, Decimal("40000"))
        self.assertEqual(cotizacion.total(), Decimal("40000"))
        confirmar(cotizacion=cotizacion)
        pedido = convertir(cotizacion=cotizacion, usuario=self.administradora)
        grande.precio = Decimal("1")
        grande.save(update_fields=["precio"])
        self.assertEqual(pedido.lineas.get().precio_acordado, Decimal("40000"))
        self.assertEqual(linea.precio_acordado, Decimal("40000"))
