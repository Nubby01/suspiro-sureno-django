import secrets

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Sum
from django.core.paginator import Paginator
from datetime import datetime, time, timedelta
from django.utils import timezone
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.catalogo.models import Producto
from apps.cuentas.models import Usuario
from apps.cuentas.permisos import RequiereRolMixin
from apps.panel.navegacion import contexto_panel
from apps.pedidos.models import EventoPedido, Pedido
from apps.pedidos.servicios import cambiar_estado

from apps.panel.demostracion import filtro_demo, criterio_demo

from .formularios import AjusteForm, EntradaForm, InsumoForm, RecetaForm, ConsumosFiltroForm
from .models import Abastecimiento, ConsumoPedido, Insumo, MovimientoInventario, Receta, RecetaIngrediente
from .servicios import agregar_ingrediente, guardar_insumo, quitar_ingrediente, registrar_movimiento

TEXTO_PRODUCCION = "Consulta los pedidos pendientes y organiza su preparación."

REGLA_PROVISIONAL = (
    "Descuento de insumos: ni la cotización ni la creación del pedido "
    "descuentan existencias. El descuento ocurre una sola vez al pasar a En preparación, "
    "solo si cada producto tiene receta completa y hay existencia suficiente. Si falta la "
    "receta, o si se trata de Rollitos de sabores, el pedido sigue pendiente y no se estiman "
    "ingredientes. Cancelar después de iniciar la preparación no devuelve existencias."
)

AVANCES = {
    Pedido.Estado.RECIBIDO: {Pedido.Estado.EN_PREPARACION},
    Pedido.Estado.EN_PREPARACION: {Pedido.Estado.LISTO},
    Pedido.Estado.LISTO: {Pedido.Estado.ENTREGADO},
}


def _panel(clave, titulo, introduccion):
    panel = dict(contexto_panel(clave))
    panel["titulo"] = titulo
    panel["introduccion"] = introduccion
    return panel


def _clave(request, nombre):
    clave = request.session.get(nombre)
    if not clave:
        clave = secrets.token_hex(16)
        request.session[nombre] = clave
    return clave


class ListaInsumosView(RequiereRolMixin, View):
    roles = (Usuario.Rol.ADMINISTRADORA,)

    def get(self, request):
        texto = (request.GET.get("q") or "").strip()
        aviso = (request.GET.get("aviso") or "").strip()
        consulta = filtro_demo(Insumo.objects.all(), request)
        if texto:
            consulta = consulta.filter(nombre__icontains=texto)
        reales = Insumo.objects.exclude(criterio_demo("nombre"))
        if aviso == "bajo":
            consulta = consulta.filter(activo=True, existencia__lte=F("stock_minimo")).exclude(
                nombre__startswith="DEMO · "
            )
        return render(
            request,
            "inventario/insumos.html",
            {
                "panel": _panel("gestion", "Inventario", "Consulta las existencias y registra los movimientos."),
                "cuenta": request.user,
                "insumos": consulta,
                "busqueda": texto,
                "aviso": aviso,
                "bajos": reales.filter(activo=True, existencia__lte=F("stock_minimo")).count(),
            },
        )


class InsumoNuevoView(RequiereRolMixin, View):
    roles = (Usuario.Rol.ADMINISTRADORA,)

    def get(self, request):
        return self._render(request, InsumoForm())

    def post(self, request):
        formulario = InsumoForm(request.POST)
        if not formulario.is_valid():
            return self._render(request, formulario)
        try:
            insumo = guardar_insumo(
                insumo=Insumo(),
                nombre=formulario.cleaned_data["nombre"],
                unidad=formulario.cleaned_data["unidad"],
                stock_minimo=formulario.cleaned_data["stock_minimo"],
                stock_critico=formulario.cleaned_data.get("stock_critico"),
                activo=formulario.cleaned_data["activo"],
            )
        except ValidationError as exc:
            formulario.add_error(None, exc)
            return self._render(request, formulario)
        messages.success(request, f"{insumo.nombre} quedó registrado con existencia 0.")
        return redirect("inventario_gestion")

    def _render(self, request, formulario):
        return render(
            request,
            "inventario/insumo_formulario.html",
            {
                "panel": _panel("gestion", "Nuevo insumo", "La existencia inicial es cero. El stock entra por un movimiento."),
                "cuenta": request.user,
                "formulario": formulario,
                "envio": "Crear insumo",
            },
        )


class InsumoEditarView(RequiereRolMixin, View):
    roles = (Usuario.Rol.ADMINISTRADORA,)

    def get(self, request, insumo_id):
        insumo = get_object_or_404(Insumo, pk=insumo_id)
        return self._render(request, insumo, InsumoForm(initial=_inicial(insumo)))

    def post(self, request, insumo_id):
        insumo = get_object_or_404(Insumo, pk=insumo_id)
        formulario = InsumoForm(request.POST)
        if not formulario.is_valid():
            return self._render(request, insumo, formulario)
        try:
            guardar_insumo(
                insumo=insumo,
                nombre=formulario.cleaned_data["nombre"],
                unidad=formulario.cleaned_data["unidad"],
                stock_minimo=formulario.cleaned_data["stock_minimo"],
                stock_critico=formulario.cleaned_data.get("stock_critico"),
                activo=formulario.cleaned_data["activo"],
            )
        except ValidationError as exc:
            formulario.add_error(None, exc)
            return self._render(request, insumo, formulario)
        messages.success(request, "El insumo quedó actualizado. La existencia no se editó desde aquí.")
        return redirect("inventario_gestion")

    def _render(self, request, insumo, formulario):
        return render(
            request,
            "inventario/insumo_formulario.html",
            {
                "panel": _panel("gestion", insumo.nombre, f"Existencia actual: {insumo.existencia} {insumo.get_unidad_display()}."),
                "cuenta": request.user,
                "formulario": formulario,
                "envio": "Guardar cambios",
                "insumo": insumo,
            },
        )


def _inicial(insumo):
    return {
        "nombre": insumo.nombre,
        "unidad": insumo.unidad,
        "stock_minimo": f"{insumo.stock_minimo:f}".rstrip("0").rstrip(".") or "0",
        "stock_critico": insumo.stock_critico,
        "activo": insumo.activo,
    }


class _MovimientoView(RequiereRolMixin, View):
    roles = (Usuario.Rol.ADMINISTRADORA,)
    formulario_clase = None
    tipo = ""
    sesion = ""
    plantilla_titulo = ""
    plantilla_intro = ""

    def get(self, request):
        formulario = self.formulario_clase(initial={"clave": _clave(request, self.sesion)})
        return self._render(request, formulario)

    def post(self, request):
        formulario = self.formulario_clase(request.POST)
        esperada = request.session.get(self.sesion)
        if not esperada or request.POST.get("clave") != esperada:
            messages.error(request, "La solicitud ya no es válida. Vuelve a enviarla.")
            return redirect(request.resolver_match.url_name)
        if not formulario.is_valid():
            return self._render(request, formulario)
        try:
            movimiento, creado = registrar_movimiento(
                insumo=formulario.cleaned_data["insumo"],
                tipo=self.tipo,
                cantidad=formulario.cleaned_data["cantidad"],
                motivo=formulario.cleaned_data["motivo"],
                usuario=request.user,
                clave=esperada,
                abastecimiento={k: formulario.cleaned_data.get(k) for k in ("es_compra", "fecha_compra", "precio_compra", "proveedor", "caducidad", "lote", "observaciones", "tipo_referencia", "referencia_compra")} if self.tipo == MovimientoInventario.Tipo.ENTRADA else None,
            )
        except ValidationError as exc:
            formulario.add_error(None, exc)
            return self._render(request, formulario)
        request.session.pop(self.sesion, None)
        if creado:
            messages.success(request, f"El movimiento quedó registrado. Existencia: {movimiento.existencia_resultante}.")
        else:
            messages.info(request, "Ese movimiento ya estaba registrado y no se aplicó de nuevo.")
        return redirect("inventario_movimientos")

    def _render(self, request, formulario):
        return render(
            request,
            "inventario/movimiento_formulario.html",
            {
                "panel": _panel("gestion", self.plantilla_titulo, self.plantilla_intro),
                "cuenta": request.user,
                "formulario": formulario,
            },
        )


class EntradaView(_MovimientoView):
    formulario_clase = EntradaForm
    tipo = MovimientoInventario.Tipo.ENTRADA
    sesion = "clave_entrada"
    plantilla_titulo = "Entrada de stock"
    plantilla_intro = "Registra una entrada con datos de compra y lote solo cuando se conozcan. La cantidad usa la unidad del insumo."


class AjusteView(_MovimientoView):
    formulario_clase = AjusteForm
    tipo = MovimientoInventario.Tipo.AJUSTE
    sesion = "clave_ajuste"
    plantilla_titulo = "Ajuste de existencia"
    plantilla_intro = "El ajuste queda auditado con motivo y responsable. No deja existencia negativa."


class MovimientosView(RequiereRolMixin, View):
    roles = (Usuario.Rol.ADMINISTRADORA,)

    def get(self, request):
        return render(
            request,
            "inventario/movimientos.html",
            {
                "panel": _panel("gestion", "Movimientos", "Cada entrada, ajuste y consumo queda registrado."),
                "cuenta": request.user,
                "movimientos": MovimientoInventario.objects.select_related("insumo", "usuario", "pedido"),
            },
        )


class ReporteConsumosView(RequiereRolMixin, View):
    roles = (Usuario.Rol.ADMINISTRADORA,)

    def get(self, request):
        formulario = ConsumosFiltroForm(request.GET)
        consulta = MovimientoInventario.objects.filter(tipo=MovimientoInventario.Tipo.CONSUMO)
        resumen = []
        if formulario.is_valid():
            datos = formulario.cleaned_data
            if not datos["incluir_demo"]:
                consulta = consulta.exclude(criterio_demo("pedido__cotizacion__observaciones"))
            if datos["fecha_inicial"]:
                inicio = timezone.make_aware(datetime.combine(datos["fecha_inicial"], time.min))
                consulta = consulta.filter(creada__gte=inicio)
            if datos["fecha_final"]:
                # Límite superior exclusivo: incluye el día final completo.
                if datos["fecha_final"].year < 9999:
                    fin = timezone.make_aware(datetime.combine(datos["fecha_final"] + timedelta(days=1), time.min))
                    consulta = consulta.filter(creada__lt=fin)
                else:
                    consulta = consulta.filter(creada__date__lte=datos["fecha_final"])
            for campo in ("insumo", "pedido"):
                if datos[campo]:
                    consulta = consulta.filter(**{campo: datos[campo]})
            resumen = list(consulta.order_by().values("insumo_id", "insumo__nombre", "insumo__unidad")
                           .annotate(consumido=-Sum("cantidad")).order_by("insumo__nombre", "insumo_id"))
        else:
            consulta = consulta.none()
        pagina = Paginator(consulta.select_related("insumo", "pedido", "usuario").annotate(
            cantidad_utilizada=-F("cantidad")).order_by("-creada", "-pk"), 50).get_page(request.GET.get("pagina"))
        parametros = request.GET.copy()
        parametros.pop("pagina", None)
        return render(request, "inventario/reporte_consumos.html", {
            "panel": _panel("gestion", "Insumos utilizados", "Consumos reales de producción por período, insumo y pedido."),
            "cuenta": request.user, "formulario": formulario, "resumen_consumos": resumen,
            "pagina": pagina, "filtros_url": parametros.urlencode(),
        })


class RecetasView(RequiereRolMixin, View):
    roles = (Usuario.Rol.ADMINISTRADORA,)

    def get(self, request):
        productos = Producto.objects.prefetch_related("recetas__ingredientes__insumo", "recetas__variante").order_by("nombre")
        return render(
            request,
            "inventario/recetas.html",
            {
                "panel": _panel(
                    "gestion",
                    "Recetas",
                    "Ninguna receta viene cargada. Un producto sin ingredientes queda pendiente de configuración.",
                ),
                "cuenta": request.user,
                "productos": productos,
                "slug_rollitos": "rollitos-de-sabores",
            },
        )

    def post(self, request):
        if request.POST.get("accion") != "quitar":
            messages.error(request, "No se reconoció la acción.")
            return redirect("inventario_recetas")
        try:
            quitar_ingrediente(ingrediente_id=request.POST.get("ingrediente"))
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        else:
            messages.success(request, "El ingrediente quedó fuera de la receta. El stock no cambió.")
        return redirect("inventario_recetas")


class RecetaNuevaView(RequiereRolMixin, View):
    roles = (Usuario.Rol.ADMINISTRADORA,)

    def get(self, request):
        return self._render(request, RecetaForm(initial={
            "producto": request.GET.get("producto"), "variante": request.GET.get("variante"),
        }))

    def post(self, request):
        formulario = RecetaForm(request.POST)
        if not formulario.is_valid():
            return self._render(request, formulario)
        try:
            agregar_ingrediente(
                producto=formulario.cleaned_data["producto"],
                variante=formulario.cleaned_data.get("variante"),
                insumo=formulario.cleaned_data["insumo"],
                cantidad=formulario.cleaned_data["cantidad"],
                rendimiento=formulario.cleaned_data["rendimiento"],
                unidad=formulario.cleaned_data["unidad"],
            )
        except ValidationError as exc:
            formulario.add_error(None, exc)
            return self._render(request, formulario)
        messages.success(request, "El ingrediente quedó en la receta. No se creó un producto nuevo.")
        return redirect("inventario_recetas")

    def _render(self, request, formulario):
        return render(
            request,
            "inventario/receta_formulario.html",
            {
                "panel": _panel("gestion", "Configurar receta", "Indica solo cantidades confirmadas. No hay recetas de ejemplo."),
                "cuenta": request.user,
                "formulario": formulario,
            },
        )


class RecetaEditarView(RecetaNuevaView):
    """Edita ingredientes con el formulario y el servicio existentes, solo administración."""

    def _cargar(self, request, receta_id):
        self.receta = get_object_or_404(
            Receta.objects.exclude(alcance__startswith="ejemplo:").select_related("producto", "variante"),
            pk=receta_id,
        )
        self.ingrediente = None
        identificador = request.GET.get("ingrediente")
        if identificador is not None:
            if not identificador.isdecimal() or len(identificador) > 18:
                raise Http404("No encontramos ese ingrediente.")
            self.ingrediente = get_object_or_404(self.receta.ingredientes, pk=identificador)

    def _formulario(self, datos=None):
        inicial = {"producto": self.receta.producto_id, "variante": self.receta.variante_id,
                   "rendimiento": self.receta.rendimiento}
        if self.ingrediente:
            inicial.update(insumo=self.ingrediente.insumo_id, cantidad=self.ingrediente.cantidad,
                           unidad=self.ingrediente.insumo.unidad)
        formulario = RecetaForm(datos, initial=inicial)
        # No aceptar que el POST traslade una receta o ingrediente a otro producto.
        for campo in ("producto", "variante"):
            formulario.fields[campo].disabled = True
        if self.ingrediente:
            formulario.fields["insumo"].disabled = True
        return formulario

    def get(self, request, receta_id):
        self._cargar(request, receta_id)
        return self._render(request, self._formulario())

    def post(self, request, receta_id):
        self._cargar(request, receta_id)
        formulario = self._formulario(request.POST)
        if formulario.is_valid():
            try:
                agregar_ingrediente(**{campo: formulario.cleaned_data.get(campo) for campo in
                    ("producto", "variante", "insumo", "cantidad", "rendimiento", "unidad")})
            except ValidationError as exc:
                formulario.add_error(None, exc)
            else:
                messages.success(request, "La receta quedó actualizada. Las existencias y los consumos anteriores no cambiaron.")
                return redirect("inventario_receta_editar", receta_id=self.receta.pk)
        return self._render(request, formulario)

    def _render(self, request, formulario):
        return render(request, "inventario/receta_editar.html", {
            "panel": _panel("gestion", "Editar receta", self.receta.producto.nombre),
            "cuenta": request.user, "receta": self.receta, "formulario": formulario,
            "ingrediente_actual": self.ingrediente,
            "ingredientes": self.receta.ingredientes.select_related("insumo"),
        })


class _ProduccionLista(RequiereRolMixin, View):
    panel_clave = "gestion"
    ruta_detalle = "produccion_gestion_detalle"

    def get(self, request):
        estado = (request.GET.get("estado") or "").strip()
        consulta = Pedido.objects.filter(
            estado__in=(Pedido.Estado.RECIBIDO, Pedido.Estado.EN_PREPARACION, Pedido.Estado.LISTO)
        ).prefetch_related("lineas")
        consulta = filtro_demo(consulta, request, "cotizacion__observaciones")
        if request.user.rol == Usuario.Rol.AYUDANTE and not request.user.is_superuser:
            consulta = consulta.filter(responsable=request.user)
        if estado in AVANCES or estado in {Pedido.Estado.EN_PREPARACION, Pedido.Estado.LISTO, Pedido.Estado.RECIBIDO}:
            if estado in Pedido.Estado.values:
                consulta = consulta.filter(estado=estado)
        return render(
            request,
            "inventario/produccion_lista.html",
            {
                "panel": _panel(self.panel_clave, "Trabajo asignado" if request.resolver_match.url_name == "trabajo_asignado" else "Producción", TEXTO_PRODUCCION),
                "regla": REGLA_PROVISIONAL,
                "cuenta": request.user,
                "pedidos": consulta,
                "estado": estado,
                "estados": [
                    (Pedido.Estado.RECIBIDO, "Recibido"),
                    (Pedido.Estado.EN_PREPARACION, "En preparación"),
                    (Pedido.Estado.LISTO, "Listo"),
                ],
                "ruta_detalle": self.ruta_detalle,
            },
        )


class _ProduccionDetalle(RequiereRolMixin, View):
    panel_clave = "gestion"
    ruta_lista = "produccion_gestion"
    ruta_detalle = "produccion_gestion_detalle"

    def _pedido(self, codigo):
        pedido = (
            Pedido.objects.filter(codigo=codigo)
            .select_related("cotizacion")
            .prefetch_related("lineas", "eventos", "eventos__usuario")
            .first()
        )
        if pedido is not None and self.request.user.rol == Usuario.Rol.AYUDANTE and not self.request.user.is_superuser and pedido.responsable_id != self.request.user.pk:
            raise Http404("No encontramos ese pedido.")
        if pedido is None:
            raise Http404("No encontramos ese pedido.")
        return pedido

    def get(self, request, codigo):
        return self._render(request, self._pedido(codigo))

    @transaction.atomic
    def post(self, request, codigo):
        Pedido.objects.select_for_update().filter(codigo=codigo).first()
        pedido = self._pedido(codigo)
        if request.POST.get("accion") == "asignar":
            if not (request.user.is_superuser or request.user.rol == Usuario.Rol.ADMINISTRADORA):
                from django.core.exceptions import PermissionDenied
                raise PermissionDenied
            responsable = request.POST.get("responsable", "").strip()
            ayudante = Usuario.objects.filter(pk=responsable, rol=Usuario.Rol.AYUDANTE, is_active=True).first() if responsable.isdecimal() else None
            if responsable and ayudante is None:
                messages.error(request, "Selecciona una ayudante activa válida.")
            elif pedido.estado in (Pedido.Estado.ENTREGADO, Pedido.Estado.CANCELADO):
                messages.error(request, "No se puede reasignar un pedido cerrado.")
            else:
                pedido.responsable = ayudante
                pedido.save(update_fields=["responsable"])
                EventoPedido.objects.create(pedido=pedido, estado_anterior=pedido.estado,
                    estado_nuevo=pedido.estado, usuario=request.user,
                    nota=f"Asignación: {ayudante.get_username() if ayudante else 'Sin asignar'}.")
                messages.success(request, "La asignación quedó guardada.")
            return redirect(self.ruta_detalle, codigo=pedido.codigo)
        estado = (request.POST.get("estado") or "").strip()
        if estado not in AVANCES.get(pedido.estado, set()):
            messages.error(request, "Ese avance no está permitido en producción.")
            return redirect(self.ruta_detalle, codigo=pedido.codigo)
        try:
            cambiar_estado(
                pedido=pedido,
                estado=estado,
                usuario=request.user,
                nota=request.POST.get("nota"),
            )
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        else:
            messages.success(request, "El avance quedó registrado.")
        return redirect(self.ruta_detalle, codigo=pedido.codigo)

    def _render(self, request, pedido):
        opciones = [
            (valor, etiqueta)
            for valor, etiqueta in Pedido.Estado.choices
            if valor in AVANCES.get(pedido.estado, set())
        ]
        return render(
            request,
            "inventario/produccion_detalle.html",
            {
                "panel": _panel(self.panel_clave, pedido.codigo, TEXTO_PRODUCCION),
                "regla": REGLA_PROVISIONAL,
                "cuenta": request.user,
                "pedido": pedido,
                "opciones": opciones,
                "ayudantes": Usuario.objects.filter(rol=Usuario.Rol.AYUDANTE, is_active=True).order_by("first_name", "username"),
                "consumo": ConsumoPedido.objects.filter(pedido=pedido).first(),
                "insumos_descontados": [
                    {"movimiento": movimiento, "cantidad": -movimiento.cantidad}
                    for movimiento in pedido.movimientos_inventario.filter(
                        tipo=MovimientoInventario.Tipo.CONSUMO,
                    ).select_related("insumo").order_by("creada", "pk")
                ],
                "ruta_lista": self.ruta_lista,
                "es_administradora": request.user.rol == Usuario.Rol.ADMINISTRADORA or request.user.is_superuser,
            },
        )


class ProduccionGestionView(_ProduccionLista):
    roles = (Usuario.Rol.ADMINISTRADORA,)
    panel_clave = "gestion"
    ruta_detalle = "produccion_gestion_detalle"


class ProduccionGestionDetalleView(_ProduccionDetalle):
    roles = (Usuario.Rol.ADMINISTRADORA,)
    panel_clave = "gestion"
    ruta_lista = "produccion_gestion"
    ruta_detalle = "produccion_gestion_detalle"


class ProduccionTrabajoView(_ProduccionLista):
    roles = (Usuario.Rol.AYUDANTE, Usuario.Rol.ADMINISTRADORA)
    panel_clave = "trabajo"
    ruta_detalle = "produccion_trabajo_detalle"


class ProduccionTrabajoDetalleView(_ProduccionDetalle):
    roles = (Usuario.Rol.AYUDANTE, Usuario.Rol.ADMINISTRADORA)
    panel_clave = "trabajo"
    ruta_lista = "produccion_trabajo"
    ruta_detalle = "produccion_trabajo_detalle"


class FichaInsumoView(RequiereRolMixin, View):
    roles = (Usuario.Rol.ADMINISTRADORA,)

    def get(self, request, insumo_id):
        from django.utils import timezone
        insumo = get_object_or_404(Insumo, pk=insumo_id)
        lotes = Abastecimiento.objects.filter(movimiento__insumo=insumo).select_related("movimiento", "movimiento__usuario")
        saldo = lotes.aggregate(total=Sum("saldo"))["total"] or 0
        proximo = lotes.filter(saldo__gt=0, caducidad__isnull=False).order_by("caducidad").first()
        return render(request, "inventario/ficha.html", {
            "panel": _panel("gestion", insumo.nombre, "Existencias y trazabilidad del abastecimiento."), "cuenta": request.user,
            "insumo": insumo, "ultima_compra": lotes.filter(es_compra=True).first(), "proximo": proximo,
            "sin_lote": max(0, insumo.existencia - saldo), "hoy": timezone.localdate(),
            "entradas": insumo.movimientos.filter(tipo=MovimientoInventario.Tipo.ENTRADA).select_related("usuario", "abastecimiento").order_by("-creada"),
        })
