"""Escritura del catálogo desde el panel.

No elimina productos. Desactivar un producto lo oculta del catálogo
público y conserva sus variantes y su galería. El precio sigue viviendo
solo en la variante.
"""

import uuid

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils.text import slugify

from .imagenes import validar_referencia
from .models import ElementoGaleria, Producto, VarianteProducto
from .servicios import (
    MENSAJE_NOMBRES_REPETIDOS,
    agregar_variante,
    crear_producto_con_variante_inicial,
    validar_producto_para_venta,
    validar_variantes,
)

MENSAJE_LISTA = "La lista enviada no coincide con el producto. No se guardó nada."
MENSAJE_NOMBRE = "Completa el nombre."


def slug_para_nombre(nombre):
    base = (slugify(nombre) or "producto")[:50]
    candidato = base
    numero = 2
    while Producto.objects.filter(slug=candidato).exists():
        sufijo = f"-{numero}"
        candidato = f"{base[: 50 - len(sufijo)]}{sufijo}"
        numero += 1
        if numero > 1000:
            raise ValidationError("No se pudo asignar un identificador al producto.")
    return candidato


@transaction.atomic
def crear_producto_simple(*, categoria, nombre, descripcion, activo, referencia_imagen, precio, precio_mayorista=None):
    nombre = (nombre or "").strip()
    if not nombre:
        raise ValidationError(MENSAJE_NOMBRE)
    return crear_producto_con_variante_inicial(
        categoria=categoria,
        nombre=nombre,
        slug=slug_para_nombre(nombre),
        precio=precio,
        precio_mayorista=precio_mayorista,
        descripcion=(descripcion or "").strip(),
        referencia_imagen=validar_referencia(referencia_imagen),
        activo=bool(activo),
        nombre_variante="",
    )


@transaction.atomic
def actualizar_producto(*, producto, nombre, descripcion, categoria, activo, referencia_imagen):
    producto = Producto.objects.select_for_update().get(pk=producto.pk)
    producto.nombre = (nombre or "").strip()
    producto.descripcion = (descripcion or "").strip()
    producto.categoria = categoria
    producto.activo = bool(activo)
    producto.referencia_imagen = validar_referencia(referencia_imagen)
    if not producto.nombre:
        raise ValidationError(MENSAJE_NOMBRE)
    producto.full_clean()
    producto.save()
    validar_producto_para_venta(producto)
    return producto


@transaction.atomic
def guardar_variantes(producto, filas):
    producto = Producto.objects.select_for_update().get(pk=producto.pk)
    bloqueadas = list(producto.variantes.select_for_update())
    por_id = {variante.pk: variante for variante in bloqueadas}
    identificadores = [fila["id"] for fila in filas]
    if len(identificadores) != len(set(identificadores)) or set(identificadores) != set(por_id):
        raise ValidationError(MENSAJE_LISTA)
    for fila in filas:
        variante = por_id[fila["id"]]
        variante.nombre = (fila["nombre"] or "").strip()
        variante.precio = fila["precio"]
        if "precio_mayorista" in fila:
            variante.precio_mayorista = fila["precio_mayorista"]
        variante.orden = fila["orden"]
        variante.activa = bool(fila["activa"])
        variante.es_predeterminada = bool(fila["es_predeterminada"])
    validar_variantes(bloqueadas, producto.activo)
    marca = uuid.uuid4().hex
    for variante in bloqueadas:
        VarianteProducto.objects.filter(pk=variante.pk).update(
            nombre=f"__tmp_{marca}_{variante.pk}__",
            es_predeterminada=False,
        )
    try:
        for variante in sorted(bloqueadas, key=lambda item: item.es_predeterminada):
            variante.save()
    except IntegrityError as exc:
        raise ValidationError(MENSAJE_NOMBRES_REPETIDOS) from exc
    validar_producto_para_venta(producto)
    return producto


def agregar_variante_panel(*, producto, nombre, precio, orden, activa, es_predeterminada, precio_mayorista=None):
    return agregar_variante(
        producto=producto,
        nombre=nombre,
        precio=precio,
        orden=orden,
        activa=activa,
        es_predeterminada=es_predeterminada,
        precio_mayorista=precio_mayorista,
    )


@transaction.atomic
def agregar_a_galeria(*, producto, producto_origen, nombre, referencia_imagen, orden):
    producto = Producto.objects.select_for_update().get(pk=producto.pk)
    if producto_origen is not None and producto_origen.pk == producto.pk:
        raise ValidationError("Un producto no puede incluirse como sabor de sí mismo.")
    referencia = validar_referencia(referencia_imagen)
    if orden is None:
        ultimo = producto.galeria.order_by("-orden", "-id").values_list("orden", flat=True).first()
        orden = 0 if ultimo is None else ultimo + 1
    elemento = ElementoGaleria(
        producto=producto,
        producto_origen=producto_origen,
        nombre=(nombre or "").strip(),
        referencia_imagen=referencia,
        orden=orden,
    )
    try:
        elemento.full_clean()
        elemento.save()
    except IntegrityError as exc:
        raise ValidationError("Ese sabor ya está en la galería del producto.") from exc
    return elemento


@transaction.atomic
def quitar_de_galeria(*, producto, elemento_id):
    try:
        identificador = int(elemento_id)
    except (TypeError, ValueError):
        raise ValidationError(MENSAJE_LISTA) from None
    elemento = (
        ElementoGaleria.objects.select_for_update().filter(pk=identificador, producto=producto).first()
    )
    if elemento is None:
        raise ValidationError(MENSAJE_LISTA)
    elemento.delete()


@transaction.atomic
def guardar_orden_galeria(*, producto, ordenes):
    producto = Producto.objects.select_for_update().get(pk=producto.pk)
    elementos = list(producto.galeria.select_for_update())
    if set(ordenes) != {elemento.pk for elemento in elementos}:
        raise ValidationError(MENSAJE_LISTA)
    for elemento in elementos:
        elemento.orden = ordenes[elemento.pk]
        elemento.save(update_fields=["orden"])
    return producto
