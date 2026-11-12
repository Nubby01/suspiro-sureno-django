from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.views import View
from datetime import timedelta
from django.utils import timezone

from apps.cuentas.models import Usuario
from apps.cuentas.permisos import RequiereRolMixin
from apps.panel.navegacion import contexto_panel

from .models import Pedido
from .servicios import TRANSICIONES, cambiar_estado


def _panel(titulo, introduccion):
    panel = dict(contexto_panel("gestion"))
    panel["titulo"] = titulo
    panel["introduccion"] = introduccion
    return panel


class MisPedidosView(LoginRequiredMixin, View):
    def get(self, request):
        pedidos = Pedido.objects.filter(cliente=request.user).select_related("cotizacion").prefetch_related("lineas")
        return render(request, "pedidos/mios.html", {"pedidos": pedidos})


class ListaPedidosView(RequiereRolMixin, View):
    roles = (Usuario.Rol.ADMINISTRADORA,)

    def get(self, request):
        estado = (request.GET.get("estado") or "").strip()
        from apps.panel.demostracion import filtro_demo
        consulta = filtro_demo(Pedido.objects.select_related("cotizacion").prefetch_related("lineas"), request, "cotizacion__observaciones")
        consulta = consulta.select_related("venta")
        if request.GET.get("ventas") == "1":
            consulta = consulta.filter(venta__isnull=False)
            if request.GET.get("periodo") == "30":
                ahora = timezone.now()
                consulta = consulta.filter(venta__fecha__gte=ahora - timedelta(days=30), venta__fecha__lte=ahora)
        if estado in Pedido.Estado.values:
            consulta = consulta.filter(estado=estado)
        return render(
            request,
            "pedidos/gestion_lista.html",
            {
                "panel": _panel("Pedidos", "Pedidos nacidos de una cotización confirmada."),
                "cuenta": request.user,
                "pedidos": consulta,
                "estado": estado,
                "estados": Pedido.Estado.choices,
            },
        )


class DetallePedidoView(RequiereRolMixin, View):
    roles = (Usuario.Rol.ADMINISTRADORA,)

    def get_pedido(self, codigo):
        pedido = (
            Pedido.objects.filter(codigo=codigo)
            .select_related("cotizacion", "venta")
            .prefetch_related("lineas", "eventos", "eventos__usuario")
            .first()
        )
        if pedido is None:
            raise Http404("No encontramos ese pedido.")
        return pedido

    def get(self, request, codigo):
        pedido = self.get_pedido(codigo)
        return self._render(request, pedido)

    def post(self, request, codigo):
        pedido = self.get_pedido(codigo)
        estado = (request.POST.get("estado") or "").strip()
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
            messages.success(request, "El estado del pedido quedó registrado.")
        return redirect("pedido_gestion", codigo=pedido.codigo)

    def _render(self, request, pedido):
        opciones = [
            (valor, etiqueta)
            for valor, etiqueta in Pedido.Estado.choices
            if valor in TRANSICIONES.get(pedido.estado, set())
        ]
        return render(
            request,
            "pedidos/gestion_detalle.html",
            {
                "panel": _panel(pedido.codigo, "El historial conserva quién cambió el estado y cuándo."),
                "cuenta": request.user,
                "pedido": pedido,
                "opciones": opciones,
            },
        )
