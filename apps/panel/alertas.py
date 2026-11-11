from django.db.models import Q, F
from apps.inventario.models import Insumo
from .demostracion import criterio_demo


def insumos_con_alerta():
    return list(Insumo.objects.filter(activo=True).exclude(criterio_demo("nombre")).filter(
        Q(existencia=0) | Q(stock_critico__isnull=False, existencia__lte=F("stock_critico"))
    ).order_by("existencia", "nombre"))
