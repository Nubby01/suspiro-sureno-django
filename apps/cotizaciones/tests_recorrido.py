"""Recorrido de cotización a entrega. Solo usa la base temporal de pruebas."""

from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.catalogo.models import Categoria
from apps.catalogo.servicios import crear_producto_con_variante_inicial
from apps.cotizaciones.models import Cotizacion
from apps.cuentas.models import Usuario
from apps.inventario.models import ConsumoPedido, Insumo, MovimientoInventario
from apps.pedidos.models import Pedido

CLAVE = "una-clave-segura-19"


class RecorridoIntegralTests(TestCase):
    def setUp(self):
        categoria = Categoria.objects.create(nombre="Alfajores", slug="alfajores", orden=1)
        self.producto = crear_producto_con_variante_inicial(
            categoria=categoria,
            nombre="Alfajor de prueba",
            slug="alfajor-de-prueba",
            precio=None,
        )
        self.variante = self.producto.variantes.get()
        self.administradora = Usuario.objects.create_user(
            "administra",
            "administra@example.com",
            CLAVE,
            rol=Usuario.Rol.ADMINISTRADORA,
        )
        self.ayudante = Usuario.objects.create_user(
            "ayuda",
            "ayuda@example.com",
            CLAVE,
            rol=Usuario.Rol.AYUDANTE,
        )
        self.clienta = Usuario.objects.create_user(
            "ana",
            "ana@example.com",
            CLAVE,
            first_name="Ana",
            last_name="Prueba",
        )
        self.otra = Usuario.objects.create_user(
            "luz",
            "luz@example.com",
            CLAVE,
        )

    def test_de_la_solicitud_a_la_entrega_sin_tocar_el_catalogo(self):
        self.assertTrue(self.client.login(username="ana@example.com", password=CLAVE))
        agregado = self.client.post(
            reverse("cotizacion_agregar"),
            {
                "variante": str(self.variante.pk),
                "cantidad": "2",
                "origen": "/catalogo/",
                "precio": "8500",
                "total": "17000",
            },
        )
        self.assertEqual(agregado.status_code, 302)
        solicitud = self.client.post(
            reverse("cotizaciones"),
            {
                "nombre": "Ana Prueba",
                "correo": "Ana@Example.com",
                "telefono": "9 1111 2222",
                "observaciones": "Recorrido de prueba.",
                "cliente": str(self.otra.pk),
                "estado": "confirmada",
                "total": "1",
            },
        )
        cotizacion = Cotizacion.objects.get()
        self.assertEqual(solicitud["Cache-Control"], "private, no-store")
        self.assertRedirects(solicitud, reverse("cotizacion_consulta", args=[cotizacion.token]))
        self.assertEqual(cotizacion.cliente_id, self.clienta.pk)
        self.assertEqual(cotizacion.correo, "ana@example.com")
        self.assertEqual(cotizacion.telefono, "+56911112222")
        self.assertEqual(cotizacion.estado, Cotizacion.Estado.SOLICITADA)
        self.assertIsNone(cotizacion.lineas.get().precio_acordado)
        consulta = self.client.get(reverse("cotizacion_consulta", args=[cotizacion.token]))
        self.assertEqual(consulta.status_code, 200)
        self.assertEqual(consulta["Cache-Control"], "private, no-store")
        self.assertEqual(consulta["Referrer-Policy"], "same-origin")

        self.client.logout()
        self.assertEqual(self.client.get(reverse("cotizaciones_gestion")).status_code, 302)
        self.assertTrue(self.client.login(username="administra", password=CLAVE))
        linea = cotizacion.lineas.get()
        precios = self.client.post(
            reverse("cotizacion_gestion", args=[cotizacion.codigo]),
            {"accion": "precios", f"precio_{linea.pk}": "2500"},
        )
        self.assertRedirects(precios, reverse("cotizacion_gestion", args=[cotizacion.codigo]))
        confirmada = self.client.post(
            reverse("cotizacion_gestion", args=[cotizacion.codigo]),
            {"accion": "confirmar"},
        )
        self.assertRedirects(confirmada, reverse("cotizacion_gestion", args=[cotizacion.codigo]))
        convertida = self.client.post(
            reverse("cotizacion_gestion", args=[cotizacion.codigo]),
            {"accion": "convertir"},
        )
        self.assertRedirects(convertida, reverse("cotizacion_gestion", args=[cotizacion.codigo]))
        repetida = self.client.post(
            reverse("cotizacion_gestion", args=[cotizacion.codigo]),
            {"accion": "convertir"},
        )
        self.assertRedirects(repetida, reverse("cotizacion_gestion", args=[cotizacion.codigo]))
        self.assertEqual(Pedido.objects.count(), 1)
        pedido = Pedido.objects.get()
        self.assertEqual(pedido.estado, Pedido.Estado.RECIBIDO)
        self.assertEqual(pedido.cliente_id, self.clienta.pk)
        self.assertEqual(pedido.total, Decimal("5000"))

        insumo_alta = self.client.post(
            reverse("inventario_nuevo"),
            {"nombre": "Harina de recorrido", "unidad": "g", "stock_minimo": "0", "activo": "on", "existencia": "500"},
        )
        self.assertRedirects(insumo_alta, reverse("inventario_gestion"))
        insumo = Insumo.objects.get()
        self.assertEqual(insumo.existencia, Decimal("0"))
        self.client.get(reverse("inventario_entrada"))
        entrada = self.client.post(
            reverse("inventario_entrada"),
            {
                "insumo": insumo.pk,
                "cantidad": "100",
                "motivo": "Compra de la prueba.",
                "clave": self.client.session["clave_entrada"],
            },
        )
        self.assertRedirects(entrada, reverse("inventario_movimientos"))
        receta = self.client.post(
            reverse("inventario_receta_nueva"),
            {
                "producto": self.producto.pk,
                "variante": "",
                "rendimiento": "1",
                "insumo": insumo.pk,
                "unidad": "g",
                "cantidad": "10",
            },
        )
        self.assertRedirects(receta, reverse("inventario_recetas"))
        asignacion = self.client.post(reverse("produccion_gestion_detalle", args=[pedido.codigo]), {"accion": "asignar", "responsable": Usuario.objects.get(username="ayuda").pk})
        self.assertRedirects(asignacion, reverse("produccion_gestion_detalle", args=[pedido.codigo]))

        self.client.logout()
        self.assertEqual(self.client.get(reverse("inventario_gestion")).status_code, 302)
        self.assertTrue(self.client.login(username="ayuda", password=CLAVE))
        self.assertEqual(self.client.get(reverse("inventario_gestion")).status_code, 403)
        preparacion = self.client.post(
            reverse("produccion_trabajo_detalle", args=[pedido.codigo]),
            {"estado": "en_preparacion", "nota": "Empieza en el taller.", "precio": "8500"},
        )
        self.assertRedirects(preparacion, reverse("produccion_trabajo_detalle", args=[pedido.codigo]))
        pedido.refresh_from_db()
        insumo.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.Estado.EN_PREPARACION)
        self.assertEqual(insumo.existencia, Decimal("80"))
        self.assertEqual(ConsumoPedido.objects.count(), 1)
        self.assertEqual(pedido.lineas.get().precio_acordado, Decimal("2500"))
        otra_vez = self.client.post(
            reverse("produccion_trabajo_detalle", args=[pedido.codigo]),
            {"estado": "en_preparacion"},
        )
        self.assertEqual(otra_vez.status_code, 302)
        insumo.refresh_from_db()
        self.assertEqual(insumo.existencia, Decimal("80"))
        self.assertEqual(MovimientoInventario.objects.filter(tipo="consumo").count(), 1)
        listo = self.client.post(
            reverse("produccion_trabajo_detalle", args=[pedido.codigo]),
            {"estado": "listo", "nota": "Quedó listo."},
        )
        self.assertRedirects(listo, reverse("produccion_trabajo_detalle", args=[pedido.codigo]))
        entregado = self.client.post(
            reverse("produccion_trabajo_detalle", args=[pedido.codigo]),
            {"estado": "entregado", "nota": "Se entregó."},
        )
        self.assertRedirects(entregado, reverse("produccion_trabajo_detalle", args=[pedido.codigo]))
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.Estado.ENTREGADO)

        self.client.logout()
        self.assertTrue(self.client.login(username="ana@example.com", password=CLAVE))
        mios = self.client.get(reverse("mis_pedidos"))
        self.assertContains(mios, pedido.codigo)
        self.assertContains(mios, "Entregado")
        self.client.logout()
        self.assertTrue(self.client.login(username="luz@example.com", password=CLAVE))
        ajenos = self.client.get(reverse("mis_pedidos"))
        self.assertNotContains(ajenos, pedido.codigo)
        self.variante.refresh_from_db()
        self.assertIsNone(self.variante.precio)
