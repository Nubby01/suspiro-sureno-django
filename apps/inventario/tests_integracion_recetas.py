from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from apps.catalogo.models import VarianteProducto
from apps.catalogo.servicios import crear_producto_con_variante_inicial
from apps.pedidos.models import Pedido
from apps.pedidos.servicios import cambiar_estado
from . import tests as base
from .models import ConsumoPedido, MovimientoInventario, Receta, RecetaIngrediente
from .servicios import agregar_ingrediente, registrar_movimiento


class IntegracionRecetasTests(TestCase):
    setUp = base.InventarioProduccionTests.setUp
    _pedido = base.InventarioProduccionTests._pedido
    _insumo = base.InventarioProduccionTests._insumo
    _entrada = base.InventarioProduccionTests._entrada
    _receta = base.InventarioProduccionTests._receta

    def receta(self):
        self.insumo = self._insumo(nombre="Harina interna QA")
        self._entrada(self.insumo, "100")
        return self._receta(cantidad="10")

    def producto_url(self):
        return reverse("catalogo_editar", args=[self.producto.pk])

    def test_consumos_reales_persisten_despues_de_editar_receta_y_avanzar(self):
        receta = self.receta()
        pedido = self._pedido(cantidad=2)
        cambiar_estado(pedido=pedido, estado="en_preparacion", usuario=self.administradora, nota="Nota de preparación QA")
        fecha = ConsumoPedido.objects.get(pedido=pedido).creada
        agregar_ingrediente(producto=self.producto, variante=None, insumo=self.insumo,
                           cantidad="40", rendimiento="1", unidad="g")
        self.client.force_login(self.administradora)
        url = reverse("produccion_gestion_detalle", args=[pedido.codigo])
        for estado in ("en_preparacion", "listo", "entregado"):
            if estado != "en_preparacion":
                self.client.post(url, {"estado": estado, "nota": "Avance QA"})
            pagina = self.client.get(url)
            self.assertContains(pagina, "Productos y cantidades solicitadas")
            self.assertContains(pagina, "Insumos descontados")
            self.assertContains(pagina, "Nota de preparación QA")
            self.assertContains(pagina, "Fecha del consumo")
            self.assertEqual(pagina.context["insumos_descontados"][0]["cantidad"], Decimal("20"))
            self.assertEqual(pagina.context["consumo"].creada, fecha)
            self.assertEqual(MovimientoInventario.objects.filter(pedido=pedido,tipo="consumo").count(), 1)
        self.insumo.refresh_from_db()
        self.assertEqual(self.insumo.existencia, Decimal("80"))

    def test_pendiente_y_movimientos_no_relacionados_no_se_presentan_como_consumo(self):
        pedido = self._pedido()
        insumo = self._insumo(nombre="Entrada ajena al consumo")
        registrar_movimiento(insumo=insumo, tipo="entrada", cantidad="10", motivo="Prueba",
                             usuario=self.administradora, clave="otra-entrada", pedido=pedido)
        self.client.force_login(self.administradora)
        pagina = self.client.get(reverse("produccion_gestion_detalle", args=[pedido.codigo]))
        self.assertContains(pagina, "Aún no se han descontado ingredientes")
        self.assertEqual(pagina.context["insumos_descontados"], [])
        self.assertFalse(ConsumoPedido.objects.exists())

    def test_consumos_solo_visibles_para_roles_y_asignaciones_autorizados(self):
        self.receta()
        propio = self._pedido()
        propio.responsable = self.ayudante
        propio.save()
        cambiar_estado(pedido=propio, estado="en_preparacion", usuario=self.administradora)
        ajeno = self._pedido()
        self.client.force_login(self.ayudante)
        self.assertContains(self.client.get(reverse("produccion_trabajo_detalle", args=[propio.codigo])), "Harina interna QA")
        self.assertEqual(self.client.get(reverse("produccion_trabajo_detalle", args=[ajeno.codigo])).status_code, 404)
        self.assertEqual(self.client.get(reverse("produccion_gestion_detalle", args=[propio.codigo])).status_code, 403)
        self.client.force_login(self.clienta)
        self.assertEqual(self.client.get(reverse("produccion_trabajo_detalle", args=[propio.codigo])).status_code, 403)

    def test_receta_general_y_especifica_por_variante(self):
        general = self.receta()
        otra = VarianteProducto.objects.create(producto=self.producto, nombre="Grande", precio=2000)
        especifica = agregar_ingrediente(producto=self.producto, variante=otra, insumo=self.insumo,
                                        cantidad="25", rendimiento="2", unidad="g")
        self.client.force_login(self.administradora)
        pagina = self.client.get(self.producto_url())
        self.assertContains(pagina, "Receta e insumos")
        self.assertContains(pagina, "Rendimiento:")
        filas = {f["variante"].pk:f for f in pagina.context["variantes_receta"]}
        self.assertEqual(filas[self.variante.pk]["receta"], general)
        self.assertEqual(filas[otra.pk]["receta"], especifica)
        self.assertTrue(all(f["configurada"] for f in filas.values()))
        self.assertContains(pagina, reverse("inventario_receta_editar",args=[especifica.pk]))

    def test_receta_especifica_vacia_no_hereda_y_demo_no_configura(self):
        self.receta()
        Receta.objects.create(producto=self.producto, variante=self.variante, rendimiento=1)
        self.client.force_login(self.administradora)
        pagina = self.client.get(self.producto_url())
        self.assertFalse(pagina.context["variantes_receta"][0]["configurada"])
        self.assertContains(pagina, "La receta vinculada aún no tiene ingredientes")
        # La receta de ejemplo permanece visible como ejemplo, sin habilitar producción real.
        self.producto.recetas.all().delete()
        demo = Receta.objects.create(producto=self.producto, rendimiento=1, alcance="ejemplo:QA")
        RecetaIngrediente.objects.create(receta=demo, insumo=self.insumo, cantidad=10)
        pagina = self.client.get(self.producto_url())
        self.assertContains(pagina, "Receta de demostración")
        self.assertFalse(pagina.context["variantes_receta"][0]["configurada"])
        self.assertEqual(self.client.get(reverse("inventario_receta_editar",args=[demo.pk])).status_code, 404)

    def test_editor_actualiza_sin_cambiar_producto_stock_o_movimientos(self):
        receta = self.receta()
        ingrediente = receta.ingredientes.get()
        otro_producto = crear_producto_con_variante_inicial(categoria=self.categoria,nombre="Otro producto",slug="otro-producto",precio=1000)
        otro_insumo = self._insumo(nombre="Otro insumo")
        self.client.force_login(self.administradora)
        url = reverse("inventario_receta_editar", args=[receta.pk]) + f"?ingrediente={ingrediente.pk}"
        self.assertContains(self.client.get(url), "Editar ingrediente")
        antes = MovimientoInventario.objects.count()
        respuesta = self.client.post(url, {"producto":otro_producto.pk,"variante":otro_producto.variantes.get().pk,
            "insumo":otro_insumo.pk,"cantidad":"15","rendimiento":"2","unidad":"g"})
        self.assertRedirects(respuesta, reverse("inventario_receta_editar",args=[receta.pk]))
        ingrediente.refresh_from_db(); receta.refresh_from_db(); self.insumo.refresh_from_db()
        self.assertEqual(ingrediente.cantidad, 15)
        self.assertEqual(ingrediente.insumo, self.insumo)
        self.assertEqual(receta.producto, self.producto)
        self.assertIsNone(receta.variante_id)
        self.assertEqual(receta.rendimiento, 2)
        self.assertEqual(self.insumo.existencia, 100)
        self.assertEqual(MovimientoInventario.objects.count(), antes)
        self.assertFalse(otro_producto.recetas.exists())

    def test_editor_rechaza_otros_roles_csrf_y_cantidades_invalidas(self):
        receta = self.receta()
        url = reverse("inventario_receta_editar",args=[receta.pk])
        for usuario in (self.ayudante,self.clienta):
            self.client.force_login(usuario)
            self.assertEqual(self.client.get(url).status_code,403)
            self.assertEqual(self.client.post(url,{}).status_code,403)
            self.assertEqual(self.client.get(self.producto_url()).status_code,403)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code,302)
        protegido = Client(enforce_csrf_checks=True)
        protegido.force_login(self.administradora)
        self.assertEqual(protegido.post(url,{}).status_code,403)
        self.client.force_login(self.administradora)
        self.assertEqual(self.client.get(url+'?ingrediente=999999').status_code,404)
        respuesta=self.client.post(url,{"insumo":self.insumo.pk,"cantidad":"0","rendimiento":"1","unidad":"g"})
        self.assertEqual(respuesta.status_code,200)
        self.assertTrue(respuesta.context["formulario"].errors)
        self.assertEqual(receta.ingredientes.get().cantidad,10)

    def test_pendiente_prefill_y_sin_recetas_en_publico(self):
        self.client.force_login(self.administradora)
        pagina=self.client.get(self.producto_url())
        self.assertContains(pagina,"Receta pendiente")
        crear=reverse("inventario_receta_nueva")+f"?producto={self.producto.pk}&variante={self.variante.pk}"
        formulario=self.client.get(crear).context["formulario"]
        self.assertEqual(formulario.initial["producto"],str(self.producto.pk))
        self.assertEqual(formulario.initial["variante"],str(self.variante.pk))
        self.receta()
        self.client.logout()
        for ruta in (reverse("catalogo"),reverse("producto_detalle",args=[self.producto.slug])):
            pagina=self.client.get(ruta)
            self.assertEqual(pagina.status_code,200)
            self.assertNotContains(pagina,"Harina interna QA")
            self.assertNotContains(pagina,"Receta e insumos")
