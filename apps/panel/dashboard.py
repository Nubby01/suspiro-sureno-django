"""Lecturas del dashboard, sin alterar pedidos ni registrar datos de visitantes."""
from datetime import timedelta

from django.db.models import Count, Sum, Min, F
from django.utils import timezone

from apps.cotizaciones.models import Cotizacion
from apps.pedidos.models import EventoPedido, LineaPedido, Pedido
from apps.pedidos.models import VentaPedido
from apps.catalogo.consultas import formato_clp
from .demostracion import criterio_demo


def entregados_en_periodo(pedidos, desde, hasta):
    # El historial aporta la fecha de entrega; una asignación posterior también
    # produce un evento, pero no debe contarse como una nueva venta.
    eventos = EventoPedido.objects.filter(
        estado_nuevo=Pedido.Estado.ENTREGADO,
        creada__gte=desde, creada__lte=hasta,
    ).exclude(estado_anterior=Pedido.Estado.ENTREGADO)
    return pedidos.filter(estado=Pedido.Estado.ENTREGADO, pk__in=eventos.values("pedido_id"))


def dashboard_gestion():
    ahora = timezone.now()
    desde = ahora - timedelta(days=30)
    pedidos = Pedido.objects.exclude(criterio_demo("cotizacion__observaciones"))
    primeras_preparaciones = EventoPedido.objects.filter(estado_nuevo=Pedido.Estado.LISTO).exclude(
        estado_anterior=F("estado_nuevo")
    ).order_by().values("pedido_id").annotate(primera=Min("creada")).filter(primera__gte=desde, primera__lte=ahora)
    preparados = list(LineaPedido.objects.filter(pedido__in=pedidos,
        pedido_id__in=primeras_preparaciones.values("pedido_id"))
        .values("variante_id", "nombre_producto", "nombre_variante")
        .annotate(unidades=Sum("cantidad")).order_by("-unidades", "nombre_producto", "variante_id")[:5])
    ventas = VentaPedido.objects.filter(pedido__in=pedidos, fecha__gte=desde, fecha__lte=ahora)
    productos = list(
        LineaPedido.objects.filter(pedido_id__in=ventas.values("pedido_id"))
        .values("nombre_producto").annotate(unidades=Sum("cantidad"))
        .order_by("-unidades", "nombre_producto")[:5]
    )
    maximo = max((p["unidades"] for p in productos), default=0)
    for producto in productos:
        producto["porcentaje"] = round(producto["unidades"] * 100 / maximo) if maximo else 0
    return {
        "ventas": ventas.count(),
        "preparados": preparados,
        "ingresos": formato_clp(ventas.aggregate(total=Sum("total"))["total"] or 0),
        "cotizaciones": Cotizacion.objects.exclude(criterio_demo("observaciones")).filter(
            creada__gte=desde, creada__lte=ahora,
        ).count(),
        "productos": productos,
        "desde": desde, "hasta": ahora,
    }


def dashboard_trabajo(usuario):
    # Se filtra SIEMPRE por responsable, incluso si entra una administradora.
    pedidos = Pedido.objects.filter(responsable=usuario).exclude(
        criterio_demo("cotizacion__observaciones")
    )
    estados = dict(pedidos.values_list("estado").annotate(cantidad=Count("pk")))
    activos = pedidos.filter(estado__in=(Pedido.Estado.RECIBIDO, Pedido.Estado.EN_PREPARACION, Pedido.Estado.LISTO))
    ahora = timezone.now()
    return {
        "asignados": activos.count(),
        "recibidos": estados.get(Pedido.Estado.RECIBIDO, 0),
        "preparacion": estados.get(Pedido.Estado.EN_PREPARACION, 0),
        "listos": estados.get(Pedido.Estado.LISTO, 0),
        "entregados": entregados_en_periodo(pedidos, ahora - timedelta(days=30), ahora).count(),
        "pedidos": list(activos.prefetch_related("lineas").order_by("creada", "id")[:5]),
    }
