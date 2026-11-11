from decimal import Decimal
from unittest.mock import patch

from django.contrib import admin
from django.db import OperationalError
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.test import Client, TestCase
from django.urls import reverse

from apps.catalogo.models import Categoria, Producto, VarianteProducto
from apps.catalogo.servicios import crear_producto_con_variante_inicial
from apps.cotizaciones.models import Cotizacion
from apps.cuentas.models import Usuario
from apps.inventario.admin import InsumoAdmin
from apps.inventario.models import ConsumoPedido, Insumo, MovimientoInventario
from apps.inventario.servicios import (
    agregar_ingrediente,
    guardar_insumo,
    registrar_movimiento,
)
from apps.pedidos.models import LineaPedido, Pedido
from apps.pedidos.servicios import cambiar_estado

CLAVE = "una-clave-segura-19"


class InventarioProduccionTests(TestCase):
    def setUp(self):
        self.categoria = Categoria.objects.create(nombre="Tortas", slug="tortas", orden=1)
        self.producto = crear_producto_con_variante_inicial(
            categoria=self.categoria,
            nombre="Torta de bizcocho",
            slug="torta-de-bizcocho",
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
            rol=Usuario.Rol.CLIENTE,
        )
        self.duena = Usuario.objects.create_superuser("duena", "duena@example.com", CLAVE)

    def _insumo(self, nombre="Harina", minimo="0"):
        return guardar_insumo(
            insumo=Insumo(),
            nombre=nombre,
            unidad=Insumo.Unidad.GRAMO,
            stock_minimo=Decimal(minimo),
            activo=True,
        )

    def _entrada(self, insumo, cantidad="100", clave="entrada-1"):
        return registrar_movimiento(
            insumo=insumo,
            tipo=MovimientoInventario.Tipo.ENTRADA,
            cantidad=Decimal(cantidad),
            motivo="Abastecimiento de prueba.",
            usuario=self.administradora,
            clave=clave,
        )

    def _receta(self, cantidad="10", rendimiento="1"):
        return agregar_ingrediente(
            producto=self.producto,
            variante=None,
            insumo=self.insumo if hasattr(self, "insumo") else Insumo.objects.get(),
            cantidad=Decimal(cantidad),
            rendimiento=Decimal(rendimiento),
            unidad=Insumo.Unidad.GRAMO,
        )

    def _pedido(self, cantidad=2, detalle="", producto=None):
        producto = producto or self.producto
        variante = producto.variantes.get()
        cotizacion = Cotizacion.objects.create(
            nombre="Ana Prueba",
            correo="ana@example.com",
            telefono="+56911112222",
            estado=Cotizacion.Estado.CONVERTIDA,
        )
        pedido = Pedido.objects.create(
            cotizacion=cotizacion,
            nombre=cotizacion.nombre,
            correo=cotizacion.correo,
            telefono=cotizacion.telefono,
            total=Decimal("1000"),
        )
        LineaPedido.objects.create(
            pedido=pedido,
            variante=variante,
            nombre_producto=producto.nombre,
            detalle=detalle,
            cantidad=cantidad,
            precio_acordado=Decimal("1000"),
        )
        return pedido

    def test_crea_edita_entrada_ajuste_y_alerta(self):
        self.client.force_login(self.administradora)
        alta = self.client.post(
            reverse("inventario_nuevo"),
            {"nombre": " Azúcar ", "unidad": "g", "stock_minimo": "1,5", "activo": "on", "existencia": "999"},
        )
        self.assertRedirects(alta, reverse("inventario_gestion"))
        insumo = Insumo.objects.get()
        self.assertEqual(insumo.nombre, "Azúcar")
        self.assertEqual(insumo.existencia, Decimal("0"))
        self.assertEqual(insumo.stock_minimo, Decimal("1.5"))
        self.assertTrue(insumo.bajo_minimo)
        lista = self.client.get(reverse("inventario_gestion"), {"aviso": "bajo"})
        self.assertContains(lista, "Bajo el mínimo")
        self.assertContains(lista, "Insumos bajo el mínimo: 1")
        self.client.get(reverse("inventario_entrada"))
        clave = self.client.session["clave_entrada"]
        entrada = self.client.post(
            reverse("inventario_entrada"),
            {"insumo": insumo.pk, "cantidad": "20", "motivo": "Compra simple.", "clave": clave},
        )
        self.assertRedirects(entrada, reverse("inventario_movimientos"))
        insumo.refresh_from_db()
        self.assertEqual(insumo.existencia, Decimal("20"))
        repetida, creada = registrar_movimiento(
            insumo=insumo,
            tipo=MovimientoInventario.Tipo.ENTRADA,
            cantidad=Decimal("20"),
            motivo="Otra vez.",
            usuario=self.administradora,
            clave=clave,
        )
        self.assertFalse(creada)
        insumo.refresh_from_db()
        self.assertEqual(insumo.existencia, Decimal("20"))
        self.assertEqual(MovimientoInventario.objects.count(), 1)
        edicion = self.client.post(
            reverse("inventario_editar", args=[insumo.pk]),
            {"nombre": "Azúcar flor", "unidad": "kg", "stock_minimo": "1", "activo": "on", "existencia": "1"},
        )
        self.assertEqual(edicion.status_code, 200)
        insumo.refresh_from_db()
        self.assertEqual(insumo.unidad, "g")
        self.assertEqual(insumo.existencia, Decimal("20"))
        self.client.post(
            reverse("inventario_editar", args=[insumo.pk]),
            {"nombre": "Azúcar flor", "unidad": "g", "stock_minimo": "5", "activo": "on"},
        )
        insumo.refresh_from_db()
        self.assertEqual(insumo.nombre, "Azúcar flor")
        self.assertEqual(insumo.existencia, Decimal("20"))
        self.client.get(reverse("inventario_ajuste"))
        ajuste = self.client.post(
            reverse("inventario_ajuste"),
            {
                "insumo": insumo.pk,
                "cantidad": "-30",
                "motivo": "Demasiado.",
                "clave": self.client.session["clave_ajuste"],
            },
        )
        self.assertEqual(ajuste.status_code, 200)
        insumo.refresh_from_db()
        self.assertEqual(insumo.existencia, Decimal("20"))
        self.client.get(reverse("inventario_ajuste"))
        self.client.post(
            reverse("inventario_ajuste"),
            {
                "insumo": insumo.pk,
                "cantidad": "-5",
                "motivo": "Merma registrada.",
                "clave": self.client.session["clave_ajuste"],
            },
        )
        insumo.refresh_from_db()
        self.assertEqual(insumo.existencia, Decimal("15"))
        self.assertEqual(self.client.post(reverse("inventario_gestion")).status_code, 405)

    def test_receta_unidad_stock_consumo_unico_y_cancelacion(self):
        insumo = self._insumo(minimo="30")
        self._entrada(insumo, "50", "entrada-base")
        self.client.force_login(self.administradora)
        unidad = self.client.post(
            reverse("inventario_receta_nueva"),
            {
                "producto": self.producto.pk,
                "rendimiento": "1",
                "insumo": insumo.pk,
                "unidad": "kg",
                "cantidad": "10",
            },
        )
        self.assertEqual(unidad.status_code, 200)
        self.assertFalse(self.producto.recetas.exists())
        self.client.post(
            reverse("inventario_receta_nueva"),
            {
                "producto": self.producto.pk,
                "rendimiento": "1",
                "insumo": insumo.pk,
                "unidad": "g",
                "cantidad": "10",
            },
        )
        self.assertEqual(Producto.objects.count(), 1)
        self.assertIsNone(self.variante.precio)
        pedido = self._pedido(cantidad=2)
        insumo.refresh_from_db()
        self.assertEqual(insumo.existencia, Decimal("50"))
        self.assertEqual(pedido.estado, Pedido.Estado.RECIBIDO)
        sin_receta = crear_producto_con_variante_inicial(
            categoria=self.categoria,
            nombre="Pie sin receta",
            slug="pie-sin-receta",
            precio=None,
        )
        pedido_sin = self._pedido(cantidad=1, producto=sin_receta)
        with self.assertRaisesMessage(ValidationError, "Falta la receta"):
            cambiar_estado(pedido=pedido_sin, estado="en_preparacion", usuario=self.administradora)
        pedido_sin.refresh_from_db()
        insumo.refresh_from_db()
        self.assertEqual(pedido_sin.estado, Pedido.Estado.RECIBIDO)
        self.assertEqual(insumo.existencia, Decimal("50"))
        self.assertEqual(MovimientoInventario.objects.filter(tipo="consumo").count(), 0)
        cambiar_estado(pedido=pedido, estado="en_preparacion", usuario=self.administradora)
        insumo.refresh_from_db()
        self.assertEqual(insumo.existencia, Decimal("30"))
        self.assertEqual(ConsumoPedido.objects.filter(pedido=pedido).count(), 1)
        self.assertEqual(MovimientoInventario.objects.filter(pedido=pedido).count(), 1)
        with self.assertRaises(ValidationError):
            cambiar_estado(pedido=pedido, estado="en_preparacion", usuario=self.administradora)
        insumo.refresh_from_db()
        self.assertEqual(insumo.existencia, Decimal("30"))
        cambiar_estado(pedido=pedido, estado="cancelado", usuario=self.administradora, nota="Se suspende.")
        insumo.refresh_from_db()
        self.assertEqual(insumo.existencia, Decimal("30"))
        registrar_movimiento(
            insumo=insumo,
            tipo=MovimientoInventario.Tipo.AJUSTE,
            cantidad=Decimal("20"),
            motivo="Devolución manual autorizada.",
            usuario=self.administradora,
            clave="ajuste-manual",
        )
        insumo.refresh_from_db()
        self.assertEqual(insumo.existencia, Decimal("50"))
        self.assertIsNone(VarianteProducto.objects.get(pk=self.variante.pk).precio)

    def test_sin_stock_sin_receta_y_rollitos_no_descuentan(self):
        insumo = self._insumo()
        self._entrada(insumo, "5", "poca")
        self.insumo = insumo
        self._receta(cantidad="10")
        pedido = self._pedido(cantidad=1)
        with self.assertRaises(ValidationError):
            cambiar_estado(pedido=pedido, estado="en_preparacion", usuario=self.administradora)
        pedido.refresh_from_db()
        insumo.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.Estado.RECIBIDO)
        self.assertEqual(insumo.existencia, Decimal("5"))
        self.assertFalse(ConsumoPedido.objects.exists())
        caja = crear_producto_con_variante_inicial(
            categoria=self.categoria,
            nombre="Rollitos de sabores",
            slug="rollitos-de-sabores",
            precio=None,
        )
        with self.assertRaises(ValidationError):
            agregar_ingrediente(
                producto=caja,
                variante=None,
                insumo=insumo,
                cantidad=Decimal("1"),
                rendimiento=Decimal("1"),
                unidad="g",
            )
        pedido_caja = self._pedido(cantidad=1, detalle="Rollo de canela y Rollo de frambuesa", producto=caja)
        with self.assertRaises(ValidationError):
            cambiar_estado(pedido=pedido_caja, estado="en_preparacion", usuario=self.ayudante)
        insumo.refresh_from_db()
        self.assertEqual(insumo.existencia, Decimal("5"))
        self.assertEqual(pedido_caja.estado, Pedido.Estado.RECIBIDO)
        self.assertEqual(Producto.objects.filter(slug="rollitos-de-sabores").count(), 1)

    def test_permisos_csrf_y_admin(self):
        self.client.force_login(self.ayudante)
        self.assertEqual(self.client.get(reverse("inventario_gestion")).status_code, 403)
        self.assertEqual(self.client.get(reverse("inventario_recetas")).status_code, 403)
        self.assertEqual(self.client.post(reverse("inventario_entrada"), {"cantidad": "1"}).status_code, 403)
        produccion = self.client.get(reverse("produccion_trabajo"))
        self.assertEqual(produccion.status_code, 200)
        self.assertNotContains(produccion, "Cotizaciones")
        self.assertNotContains(produccion, "Inventario")
        self.client.force_login(self.clienta)
        self.assertEqual(self.client.get(reverse("produccion_gestion")).status_code, 403)
        self.assertEqual(self.client.get(reverse("produccion_trabajo")).status_code, 403)
        self.client.logout()
        anonimo = self.client.get(reverse("inventario_gestion"))
        self.assertEqual(anonimo.status_code, 302)
        self.assertIn("/cuenta/ingresar/", anonimo["Location"])
        protegido = Client(enforce_csrf_checks=True)
        protegido.force_login(self.administradora)
        rechazo = protegido.post(
            reverse("inventario_nuevo"),
            {"nombre": "Intruso", "unidad": "g", "stock_minimo": "0", "activo": "on"},
        )
        self.assertEqual(rechazo.status_code, 403)
        self.assertFalse(Insumo.objects.filter(nombre="Intruso").exists())
        self.client.force_login(self.duena)
        self.assertEqual(self.client.get("/admin/inventario/insumo/add/").status_code, 200)
        self.client.post(
            "/admin/inventario/insumo/add/",
            {"nombre": "Cacao", "unidad": "g", "stock_minimo": "0", "activo": "on"},
        )
        cacao = Insumo.objects.get(nombre="Cacao")
        self.assertEqual(cacao.existencia, Decimal("0"))
        ajuste = self.client.post(
            "/admin/inventario/movimientoinventario/add/",
            {
                "insumo": cacao.pk,
                "tipo": "ajuste",
                "cantidad": "-5",
                "motivo": "No debería quedar negativo.",
                "clave_solicitud": "admin-negativo",
            },
        )
        self.assertEqual(ajuste.status_code, 200)
        cacao.refresh_from_db()
        self.assertEqual(cacao.existencia, Decimal("0"))
        self._entrada(cacao, "4", "entrada-cacao")
        self.assertFalse(InsumoAdmin(Insumo, admin.site).has_delete_permission(None, cacao))
        with self.assertRaises(ProtectedError):
            cacao.delete()
        self.client.force_login(self.clienta)
        self.assertEqual(self.client.get("/admin/inventario/insumo/add/").status_code, 403)

    def test_ayudante_registra_avance_y_no_cambia_precios(self):
        insumo = self._insumo()
        self._entrada(insumo, "100", "entrada-ayuda")
        self.insumo = insumo
        self._receta()
        pedido = self._pedido(cantidad=1)
        pedido.responsable = self.ayudante
        pedido.save(update_fields=["responsable"])
        self.client.force_login(self.ayudante)
        detenido = self.client.post(
            reverse("produccion_trabajo_detalle", args=[pedido.codigo]),
            {"estado": "cancelado", "nota": "No me corresponde.", "precio": "8500"},
        )
        self.assertEqual(detenido.status_code, 302)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.Estado.RECIBIDO)
        self.assertEqual(pedido.lineas.get().precio_acordado, Decimal("1000"))
        self.client.post(
            reverse("produccion_trabajo_detalle", args=[pedido.codigo]),
            {"estado": "en_preparacion", "nota": "Empieza en el taller.", "precio": "10500"},
        )
        pedido.refresh_from_db()
        insumo.refresh_from_db()
        self.assertEqual(pedido.estado, Pedido.Estado.EN_PREPARACION)
        self.assertEqual(insumo.existencia, Decimal("90"))
        self.assertEqual(pedido.lineas.get().precio_acordado, Decimal("1000"))
        self.assertIsNone(self.variante.precio)
        repetido = self.client.post(
            reverse("produccion_trabajo_detalle", args=[pedido.codigo]),
            {"estado": "en_preparacion"},
        )
        self.assertEqual(repetido.status_code, 302)
        insumo.refresh_from_db()
        self.assertEqual(insumo.existencia, Decimal("90"))
        self.client.force_login(self.clienta)
        self.assertEqual(
            self.client.get(reverse("produccion_trabajo_detalle", args=[pedido.codigo])).status_code,
            403,
        )

    def test_cantidad_demasiado_grande_no_crea_movimiento(self):
        self.client.force_login(self.administradora)
        insumo = self._insumo()
        self.client.get(reverse("inventario_entrada"))
        respuesta = self.client.post(
            reverse("inventario_entrada"),
            {
                "insumo": insumo.pk,
                "cantidad": "9" * 20,
                "motivo": "Cantidad imposible.",
                "clave": self.client.session["clave_entrada"],
            },
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "hasta 3 decimales")
        self.assertEqual(MovimientoInventario.objects.count(), 0)
        insumo.refresh_from_db()
        self.assertEqual(insumo.existencia, Decimal("0"))

    def test_bloqueo_de_sqlite_no_aplica_el_movimiento(self):
        insumo = self._insumo()
        with patch(
            "apps.inventario.servicios.Insumo.objects.select_for_update",
            side_effect=OperationalError("database is locked"),
        ):
            with self.assertRaisesMessage(ValidationError, "Intenta nuevamente"):
                registrar_movimiento(
                    insumo=insumo,
                    tipo=MovimientoInventario.Tipo.ENTRADA,
                    cantidad="5",
                    motivo="Compra interrumpida.",
                    usuario=self.administradora,
                    clave="entrada-bloqueada",
                )
        self.assertEqual(MovimientoInventario.objects.count(), 0)
        insumo.refresh_from_db()
        self.assertEqual(insumo.existencia, Decimal("0"))
