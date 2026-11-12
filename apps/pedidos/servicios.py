"""Pedidos que nacen de una cotización confirmada.

Crear el pedido no descuenta inventario. El descuento ocurre solo al pasar
a «En preparación», mediante las reglas provisionales de inventario.
"""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, OperationalError, transaction
from django.db.models import F
from django.utils import timezone

from apps.cotizaciones.models import Cotizacion
from apps.cotizaciones.servicios import MENSAJE_PENDIENTE

from .models import EventoPedido, LineaPedido, Pedido, VentaPedido


def registrar_venta(*, pedido, usuario=None):
    """Reconoce el ingreso completo una vez, sin modificar precios ni existencias.

    La operación normal llama dentro de la transacción y bloqueo del pedido.
    Si se repara un pedido antiguo se toma su primer evento comercial real.
    """
    evento = pedido.eventos.filter(estado_nuevo__in=(Pedido.Estado.RECIBIDO, Pedido.Estado.ENTREGADO)).exclude(
        estado_anterior=F("estado_nuevo")
    ).order_by("creada", "pk").first()
    if evento is None and pedido.estado not in (Pedido.Estado.RECIBIDO, Pedido.Estado.ENTREGADO):
        return None
    venta, _ = VentaPedido.objects.get_or_create(pedido=pedido, defaults={
        "total": pedido.total,
        "fecha": evento.creada if evento else pedido.creada or timezone.now(),
        "usuario": evento.usuario if evento else usuario if getattr(usuario, "is_authenticated", False) else None,
        "estado_origen": evento.estado_nuevo if evento else pedido.estado,
        "fecha_estimada": evento is None,
    })
    return venta

MENSAJE_DUPLICADO = "Esta cotización ya tiene un pedido."
MENSAJE_NO_CONFIRMADA = "Solo se puede convertir una cotización confirmada."
MENSAJE_TRANSICION = "Ese cambio de estado no está permitido."
MENSAJE_CANCELACION = "Indica el motivo de la cancelación."

TRANSICIONES = {
    Pedido.Estado.RECIBIDO: {Pedido.Estado.EN_PREPARACION, Pedido.Estado.CANCELADO},
    Pedido.Estado.EN_PREPARACION: {Pedido.Estado.LISTO, Pedido.Estado.CANCELADO},
    Pedido.Estado.LISTO: {Pedido.Estado.ENTREGADO, Pedido.Estado.CANCELADO},
    Pedido.Estado.ENTREGADO: set(),
    Pedido.Estado.CANCELADO: set(),
}


def convertir(*, cotizacion, usuario):
    try:
        with transaction.atomic():
            return _convertir_confirmada(cotizacion=cotizacion, usuario=usuario)
    except OperationalError as exc:
        raise ValidationError("No se pudo convertir la cotización. Intenta nuevamente.") from exc


def _convertir_confirmada(*, cotizacion, usuario):
    cotizacion = Cotizacion.objects.select_for_update().get(pk=cotizacion.pk)
    if Pedido.objects.filter(cotizacion=cotizacion).exists():
        raise ValidationError(MENSAJE_DUPLICADO)
    if cotizacion.estado != Cotizacion.Estado.CONFIRMADA:
        raise ValidationError(MENSAJE_NO_CONFIRMADA)
    lineas = list(cotizacion.lineas.select_for_update())
    if any(linea.precio_acordado is None for linea in lineas):
        raise ValidationError(MENSAJE_PENDIENTE)
    total = sum((linea.precio_acordado * linea.cantidad for linea in lineas), start=0)
    pedido = Pedido(
        cotizacion=cotizacion,
        cliente=cotizacion.cliente,
        nombre=cotizacion.nombre,
        correo=cotizacion.correo,
        telefono=cotizacion.telefono,
        total=total,
    )
    try:
        with transaction.atomic():
            pedido.save()
    except IntegrityError as exc:
        raise ValidationError(MENSAJE_DUPLICADO) from exc
    for linea in lineas:
        LineaPedido.objects.create(
            pedido=pedido,
            variante=linea.variante,
            nombre_producto=linea.nombre_producto,
            nombre_variante=linea.nombre_variante,
            detalle=linea.detalle,
            cantidad=linea.cantidad,
            precio_acordado=linea.precio_acordado,
        )
    cotizacion.estado = Cotizacion.Estado.CONVERTIDA
    cotizacion.save(update_fields=["estado"])
    EventoPedido.objects.create(
        pedido=pedido,
        estado_anterior="",
        estado_nuevo=Pedido.Estado.RECIBIDO,
        usuario=usuario if getattr(usuario, "is_authenticated", False) else None,
        nota="Pedido creado desde la cotización.",
    )
    registrar_venta(pedido=pedido, usuario=usuario)
    return pedido


def cambiar_estado(*, pedido, estado, usuario, nota=""):
    try:
        with transaction.atomic():
            return _cambiar_estado(pedido=pedido, estado=estado, usuario=usuario, nota=nota)
    except OperationalError as exc:
        raise ValidationError("No se pudo registrar el cambio. Intenta nuevamente.") from exc


def _cambiar_estado(*, pedido, estado, usuario, nota):
    pedido = Pedido.objects.select_for_update().get(pk=pedido.pk)
    if estado not in TRANSICIONES.get(pedido.estado, set()):
        raise ValidationError(MENSAJE_TRANSICION)
    nota = (nota or "").strip()
    if estado == Pedido.Estado.CANCELADO and not nota:
        raise ValidationError(MENSAJE_CANCELACION)
    if estado == Pedido.Estado.EN_PREPARACION:
        from apps.inventario.servicios import consumir_para_preparacion

        consumir_para_preparacion(pedido=pedido, usuario=usuario)
    anterior = pedido.estado
    if anterior == Pedido.Estado.RECIBIDO:
        registrar_venta(pedido=pedido, usuario=usuario)
    pedido.estado = estado
    pedido.save(update_fields=["estado"])
    EventoPedido.objects.create(
        pedido=pedido,
        estado_anterior=anterior,
        estado_nuevo=estado,
        usuario=usuario if getattr(usuario, "is_authenticated", False) else None,
        nota=nota[:500],
    )
    if estado in (Pedido.Estado.RECIBIDO, Pedido.Estado.ENTREGADO):
        registrar_venta(pedido=pedido, usuario=usuario)
    return pedido
