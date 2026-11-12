"""La protección no guarda ni carga el recetario real: usa datos aislados de QA."""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.catalogo.models import Categoria, Producto, VarianteProducto
from apps.cotizaciones.models import Cotizacion
from apps.cotizaciones.servicios import solicitar, confirmar
from apps.cuentas.models import Usuario
from apps.pedidos.models import Pedido, LineaPedido, EventoPedido, VentaPedido
from apps.pedidos.servicios import cambiar_estado, convertir
from .models import Insumo, Receta, RecetaIngrediente, ConsumoPedido, MovimientoInventario
from .servicios import consumir_para_preparacion, MENSAJE_ROLLITOS


class BloqueoRellenosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        categoria=Categoria.objects.create(nombre="Productos QA",slug="productos-qa")
        cls.admin=Usuario.objects.create_user("admin-bloqueo",rol=Usuario.Rol.ADMINISTRADORA)
        cls.ayudante=Usuario.objects.create_user("ayuda-bloqueo",rol=Usuario.Rol.AYUDANTE)
        cls.insumo=Insumo.objects.create(nombre="Harina QA",unidad="g",existencia=100)
        cls.demo=Insumo.objects.create(nombre="DEMO · Harina QA",unidad="g",existencia=100)
        cls.variantes={}
        for identificador,slug,nombre in ((1,"alfajor-brownie-con-relleno","Alfajor brownie con relleno"),
            (5,"berlines","Berlines"),(27,"rollitos-de-sabores","Rollitos de sabores"),
            (90,"producto-fijo-qa","Producto fijo QA")):
            producto=Producto.objects.create(categoria=categoria,slug=slug,nombre=nombre)
            variante=VarianteProducto.objects.create(id=identificador,producto=producto,
                nombre="Caja de 4" if identificador in (5,27) else "",precio=1000,es_predeterminada=True)
            cls.variantes[identificador]=variante
            for demo in (False,True):
                # Simula incluso una receta antigua ya vinculada: el bloqueo
                # debe preceder su selección/validación y no confiar en su ausencia.
                receta=Receta.objects.create(producto=producto,variante=variante,rendimiento=1,
                    alcance=f"ejemplo:v{identificador}" if demo else "")
                RecetaIngrediente.objects.create(receta=receta,insumo=cls.demo if demo else cls.insumo,cantidad=10)

    def pedido(self,identificador,demo=False,mixto=False,fijo_primero=True):
        cotizacion=Cotizacion.objects.create(nombre="QA",correo="qa@example.com",telefono="+56900000000",
            observaciones="DEMO · QA" if demo else "")
        pedido=Pedido.objects.create(cotizacion=cotizacion,nombre="QA",correo="qa@example.com",
            telefono="+56900000000",total=2000,responsable=self.ayudante)
        ids=([90,identificador] if fijo_primero else [identificador,90]) if mixto else [identificador]
        for numero in ids:
            variante=self.variantes[numero]
            LineaPedido.objects.create(pedido=pedido,variante=variante,nombre_producto=variante.producto.nombre,
                nombre_variante=variante.nombre,detalle="Manjar y Pastelera" if numero==5 else "Café",
                cantidad=2,precio_acordado=1000)
        return pedido

    def comprobar_sin_consumo(self,pedido):
        pedido.refresh_from_db();self.insumo.refresh_from_db();self.demo.refresh_from_db()
        self.assertEqual(pedido.estado,"recibido")
        self.assertEqual(self.insumo.existencia,Decimal("100"))
        self.assertEqual(self.demo.existencia,Decimal("100"))
        self.assertFalse(ConsumoPedido.objects.filter(pedido=pedido).exists())
        self.assertFalse(MovimientoInventario.objects.filter(pedido=pedido).exists())
        self.assertFalse(EventoPedido.objects.filter(pedido=pedido,estado_nuevo="en_preparacion").exists())

    def test_variante_1_y_5_bloqueadas_con_recetas_comerciales_y_demo(self):
        for identificador in (1,5):
            for demo in (False,True):
                with self.subTest(variante=identificador,demo=demo):
                    pedido=self.pedido(identificador,demo)
                    with self.assertRaisesMessage(ValidationError,"composición necesita definirse"):
                        consumir_para_preparacion(pedido=pedido,usuario=self.admin)
                    with self.assertRaisesMessage(ValidationError,"composición necesita definirse"):
                        cambiar_estado(pedido=pedido,estado="en_preparacion",usuario=self.admin,nota="Intento QA")
                    self.comprobar_sin_consumo(pedido)

    def test_rollitos_mantiene_el_mismo_bloqueo_con_ambos_tipos_de_receta(self):
        for demo in (False,True):
            pedido=self.pedido(27,demo)
            with self.assertRaisesMessage(ValidationError,MENSAJE_ROLLITOS):
                cambiar_estado(pedido=pedido,estado="en_preparacion",usuario=self.admin)
            self.comprobar_sin_consumo(pedido)

    def test_bloqueo_no_depende_de_que_haya_receta(self):
        Receta.objects.filter(variante_id__in=(1,5)).delete()
        for identificador in (1,5):
            pedido=self.pedido(identificador)
            with self.assertRaisesMessage(ValidationError,"composición necesita definirse"):
                cambiar_estado(pedido=pedido,estado="en_preparacion",usuario=self.admin)
            self.comprobar_sin_consumo(pedido)

    def test_pedidos_mixtos_no_aplican_consumos_parciales_en_ningun_orden(self):
        for identificador in (1,5,27):
            for demo in (False,True):
                for primero in (False,True):
                    pedido=self.pedido(identificador,demo,mixto=True,fijo_primero=primero)
                    with self.assertRaises(ValidationError):
                        cambiar_estado(pedido=pedido,estado="en_preparacion",usuario=self.admin)
                    self.comprobar_sin_consumo(pedido)

    def test_productos_fijos_siguen_descontando_una_sola_vez(self):
        for demo in (False,True):
            pedido=self.pedido(90,demo)
            for estado in ("en_preparacion","listo","entregado"):
                cambiar_estado(pedido=pedido,estado=estado,usuario=self.admin)
            insumo=self.demo if demo else self.insumo
            insumo.refresh_from_db()
            self.assertEqual(insumo.existencia,80)
            self.assertEqual(ConsumoPedido.objects.filter(pedido=pedido).count(),1)
            self.assertEqual(MovimientoInventario.objects.filter(pedido=pedido,tipo="consumo").count(),1)

    def test_catalogo_carrito_cotizacion_conversion_y_venta_siguen_disponibles(self):
        for identificador,sabores in ((1,["cafe"]),(5,["manjar","pastelera"])):
            variante=self.variantes[identificador]
            self.assertContains(self.client.get(reverse("producto_detalle",args=[variante.producto.slug])),variante.producto.nombre)
            datos={"variante":variante.pk,"cantidad":"1"}
            datos.update({"sabor_brownie":"cafe"} if identificador==1 else {"sabor_1":"manjar","sabor_2":"pastelera"})
            from apps.cotizaciones.carrito import agregar,leer
            from django.test import RequestFactory
            from django.contrib.sessions.backends.db import SessionStore
            request=RequestFactory().post("/")
            request.session=SessionStore()
            agregar(request,variante.pk,1,sabores)
            self.assertEqual(leer(request)[0]["sabores"],sabores)
            cotizacion=solicitar(cliente=None,nombre="QA",correo="qa@example.com",telefono="+56900000000",observaciones="",
                lineas=[{"variante_id":variante.pk,"cantidad":1,"sabores":sabores}])
            confirmar(cotizacion=cotizacion)
            pedido=convertir(cotizacion=cotizacion,usuario=self.admin)
            self.assertEqual(pedido.estado,"recibido")
            self.assertEqual(pedido.lineas.get().detalle,"Café" if identificador==1 else "Manjar y Pastelera")
            self.assertTrue(VentaPedido.objects.filter(pedido=pedido).exists())
            self.assertFalse(ConsumoPedido.objects.filter(pedido=pedido).exists())
            venta=VentaPedido.objects.get(pedido=pedido)
            anterior=(venta.pk,venta.total,venta.fecha)
            with self.assertRaisesMessage(ValidationError,"composición necesita definirse"):
                cambiar_estado(pedido=pedido,estado="en_preparacion",usuario=self.admin)
            venta.refresh_from_db()
            self.assertEqual((venta.pk,venta.total,venta.fecha),anterior)

    def test_interfaz_admin_y_ayudante_muestra_error_controlado(self):
        for usuario,ruta in ((self.admin,"produccion_gestion_detalle"),(self.ayudante,"produccion_trabajo_detalle")):
            pedido=self.pedido(1)
            self.client.force_login(usuario)
            respuesta=self.client.post(reverse(ruta,args=[pedido.codigo]),{"estado":"en_preparacion","nota":"QA"},follow=True)
            self.assertEqual(respuesta.status_code,200)
            self.assertContains(respuesta,"composición necesita definirse")
            self.comprobar_sin_consumo(pedido)
