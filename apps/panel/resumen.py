"""Indicadores reales del panel. Los ejemplos DEMO se cuentan aparte."""

from django.db.models import F, Sum
from .demostracion import criterio_demo

from apps.cotizaciones.models import Cotizacion, LineaCotizacion
from apps.inventario.models import Insumo
from apps.pedidos.models import Pedido

MARCA_DEMO = "DEMO · "


def resumen_gestion():
    cotizaciones = Cotizacion.objects.exclude(criterio_demo("observaciones"))
    pedidos = Pedido.objects.exclude(criterio_demo("cotizacion__observaciones"))
    return {
        "cotizaciones_abiertas": cotizaciones.filter(estado__in=Cotizacion.ABIERTAS).count(),
        "pedidos": {
            "recibido": pedidos.filter(estado=Pedido.Estado.RECIBIDO).count(),
            "en_preparacion": pedidos.filter(estado=Pedido.Estado.EN_PREPARACION).count(),
            "listo": pedidos.filter(estado=Pedido.Estado.LISTO).count(),
            "entregado": pedidos.filter(estado=Pedido.Estado.ENTREGADO).count(),
        },
        "alertas_stock": list(Insumo.objects.filter(activo=True, existencia__lte=F("stock_minimo")).exclude(criterio_demo("nombre")).order_by("existencia", "nombre")),
        "bajos": Insumo.objects.filter(activo=True, existencia__lte=F("stock_minimo"))
        .exclude(criterio_demo("nombre"))
        .count(),
        "recientes": list(pedidos.select_related("cotizacion").order_by("-creada")[:5]),
        "solicitados": list(
            LineaCotizacion.objects.exclude(criterio_demo("cotizacion__observaciones"))
            .values("nombre_producto")
            .annotate(total=Sum("cantidad"))
            .order_by("-total", "nombre_producto")[:5]
        ),
        "demo_pedidos": Pedido.objects.filter(criterio_demo("cotizacion__observaciones")).count(),
        "demo_cotizaciones": Cotizacion.objects.filter(criterio_demo("observaciones")).count(),
    }
