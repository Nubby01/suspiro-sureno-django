"""Reglas de la cotización. Los precios del catálogo no se modifican."""

import re

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.catalogo.berlines import NOMBRES as SABORES_BERLIN
from apps.catalogo.berlines import SLUG as SLUG_BERLIN
from apps.catalogo.brownie import NOMBRES as CENTROS_BROWNIE
from apps.catalogo.brownie import SLUG as SLUG_BROWNIE
from apps.catalogo.models import Producto, VarianteProducto
from apps.catalogo.rollitos import SABORES, SLUG as SLUG_ROLLITOS
from apps.cuentas.servicios import normalizar_correo, normalizar_telefono

from .models import Cotizacion, LineaCotizacion

MENSAJE_CANTIDAD = "La cantidad debe ser un número entero entre 1 y 99."
MENSAJE_PRODUCTO = "Ese producto no está disponible."
MENSAJE_SABORES = "Indica uno o dos sabores publicados para la caja de cuatro."
MENSAJE_SABORES_AJENOS = "Solo la caja de Rollitos de sabores admite una combinación de sabores."
MENSAJE_BERLINES = "Indica uno o dos sabores de la caja de berlines."
MENSAJE_CENTRO = "Elige uno de los centros del alfajor brownie."
MENSAJE_CERRADA = "Esta cotización ya no admite ese cambio."
MENSAJE_PENDIENTE = "No se puede confirmar mientras haya precios pendientes."
MENSAJE_MOTIVO = "Indica el motivo."
MENSAJE_LISTA = "La lista de productos no coincide con la cotización."


def cantidad_valida(valor):
    texto = str(valor or "").strip()
    if not re.fullmatch(r"\d{1,2}", texto):
        raise ValidationError(MENSAJE_CANTIDAD)
    numero = int(texto)
    if not 1 <= numero <= 99:
        raise ValidationError(MENSAJE_CANTIDAD)
    return numero


def variante_publica(identificador):
    try:
        pk = int(identificador)
    except (TypeError, ValueError):
        raise ValidationError(MENSAJE_PRODUCTO) from None
    variante = (
        VarianteProducto.objects.select_related("producto", "producto__categoria")
        .filter(
            pk=pk,
            activa=True,
            producto__activo=True,
            producto__categoria__activa=True,
        )
        .first()
    )
    if variante is None:
        raise ValidationError(MENSAJE_PRODUCTO)
    return variante


def detalle_centro_brownie(variante, codigo):
    """Un centro fijo del brownie. No acepta texto libre ni cambia el precio."""
    codigo = (codigo or "").strip()
    if variante.producto.slug != SLUG_BROWNIE:
        if codigo:
            raise ValidationError(MENSAJE_CENTRO)
        return ""
    nombre = CENTROS_BROWNIE.get(codigo)
    if nombre is None:
        raise ValidationError(MENSAJE_CENTRO)
    return nombre


def detalle_sabores(variante, primero, segundo):
    if variante.producto.slug == SLUG_BERLIN:
        return _detalle_codigos(primero, segundo, SABORES_BERLIN, MENSAJE_BERLINES)
    if variante.producto.slug != SLUG_ROLLITOS:
        if (primero or "").strip() or (segundo or "").strip():
            raise ValidationError(MENSAJE_SABORES_AJENOS)
        return ""
    pedidos = []
    for sabor in (primero, segundo):
        slug = (sabor or "").strip()
        if not slug or slug in pedidos:
            continue
        if slug not in SABORES:
            raise ValidationError(MENSAJE_SABORES)
        pedidos.append(slug)
    if not 1 <= len(pedidos) <= 2:
        raise ValidationError(MENSAJE_SABORES)
    origenes = {
        producto.slug: producto.nombre
        for producto in Producto.objects.filter(slug__in=pedidos, activo=True)
    }
    if len(origenes) != len(pedidos):
        raise ValidationError(MENSAJE_SABORES)
    nombres = [origenes[slug] for slug in pedidos]
    if len(nombres) == 1:
        return nombres[0]
    return f"{nombres[0]} y {nombres[1]}"


def _detalle_codigos(primero, segundo, nombres, mensaje):
    pedidos = []
    for sabor in (primero, segundo):
        codigo = (sabor or "").strip()
        if not codigo or codigo in pedidos:
            continue
        if codigo not in nombres:
            raise ValidationError(mensaje)
        pedidos.append(codigo)
    if not 1 <= len(pedidos) <= 2:
        raise ValidationError(mensaje)
    etiquetas = [nombres[codigo] for codigo in pedidos]
    if len(etiquetas) == 1:
        return etiquetas[0]
    return f"{etiquetas[0]} y {etiquetas[1]}"


def detalle_desde_slugs(variante, sabores):
    sabores = list(sabores or [])
    if variante.producto.slug == SLUG_BROWNIE:
        if len(sabores) != 1:
            raise ValidationError(MENSAJE_CENTRO)
        return detalle_centro_brownie(variante, sabores[0])
    primero = sabores[0] if sabores else ""
    segundo = sabores[1] if len(sabores) > 1 else ""
    return detalle_sabores(variante, primero, segundo)


def _linea_nueva(cotizacion, variante, cantidad, detalle):
    return LineaCotizacion(
        cotizacion=cotizacion,
        variante=variante,
        nombre_producto=variante.producto.nombre,
        nombre_variante=(variante.nombre or "").strip(),
        detalle=detalle,
        cantidad=cantidad,
        precio_acordado=variante.precio,
    )


@transaction.atomic
def solicitar(*, cliente, nombre, correo, telefono, observaciones, lineas):
    if not lineas:
        raise ValidationError("Agrega al menos un producto a la cotización.")
    nombre = (nombre or "").strip()
    if not nombre:
        raise ValidationError("Completa el nombre.")
    cotizacion = Cotizacion(
        cliente=cliente if getattr(cliente, "is_authenticated", False) else None,
        nombre=nombre[:120],
        correo=normalizar_correo(correo),
        telefono=normalizar_telefono(telefono),
        observaciones=(observaciones or "").strip()[:1000],
    )
    for _ in range(3):
        try:
            with transaction.atomic():
                cotizacion.save()
            break
        except IntegrityError:
            cotizacion.pk = None
            cotizacion.codigo = ""
            cotizacion.token = ""
    else:
        raise ValidationError("No se pudo crear la cotización. Intenta nuevamente.")
    for item in lineas:
        variante = variante_publica(item["variante_id"])
        detalle = detalle_desde_slugs(variante, item.get("sabores"))
        linea = _linea_nueva(cotizacion, variante, item["cantidad"], detalle)
        linea.full_clean()
        linea.save()
    return cotizacion


@transaction.atomic
def fijar_precios(*, cotizacion, precios):
    cotizacion = Cotizacion.objects.select_for_update().get(pk=cotizacion.pk)
    if cotizacion.estado not in Cotizacion.ABIERTAS:
        raise ValidationError(MENSAJE_CERRADA)
    lineas = {linea.pk: linea for linea in cotizacion.lineas.select_for_update()}
    if set(precios) != set(lineas):
        raise ValidationError(MENSAJE_LISTA)
    for pk, precio in precios.items():
        lineas[pk].precio_acordado = precio
        lineas[pk].full_clean()
        lineas[pk].save(update_fields=["precio_acordado"])
    if cotizacion.estado == Cotizacion.Estado.SOLICITADA:
        cotizacion.estado = Cotizacion.Estado.EN_REVISION
        cotizacion.save(update_fields=["estado"])
    return cotizacion


@transaction.atomic
def confirmar(*, cotizacion):
    cotizacion = Cotizacion.objects.select_for_update().prefetch_related("lineas").get(pk=cotizacion.pk)
    if cotizacion.estado not in Cotizacion.ABIERTAS:
        raise ValidationError(MENSAJE_CERRADA)
    if cotizacion.total() is None:
        raise ValidationError(MENSAJE_PENDIENTE)
    cotizacion.estado = Cotizacion.Estado.CONFIRMADA
    cotizacion.save(update_fields=["estado"])
    return cotizacion


@transaction.atomic
def cerrar(*, cotizacion, estado, motivo):
    if estado not in (Cotizacion.Estado.RECHAZADA, Cotizacion.Estado.CANCELADA):
        raise ValidationError(MENSAJE_CERRADA)
    cotizacion = Cotizacion.objects.select_for_update().get(pk=cotizacion.pk)
    permitidos = set(Cotizacion.ABIERTAS)
    if estado == Cotizacion.Estado.CANCELADA:
        permitidos.add(Cotizacion.Estado.CONFIRMADA)
    if cotizacion.estado not in permitidos:
        raise ValidationError(MENSAJE_CERRADA)
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValidationError(MENSAJE_MOTIVO)
    cotizacion.estado = estado
    cotizacion.motivo = motivo[:500]
    cotizacion.save(update_fields=["estado", "motivo"])
    return cotizacion
