"""Operaciones de catálogo que cruzan más de una fila.

La base garantiza el precio no negativo, como máximo una predeterminada
por producto y la unicidad del nombre normalizado. No garantiza que un
producto activo tenga una variante vendible: eso solo ocurre cuando la
escritura pasa por estas funciones o por el admin, que las reutiliza.

`QuerySet.update()`, el SQL directo y `save()` suelto no ejecutan estas
validaciones. `save()` tampoco ejecuta `full_clean()` por sí solo.
"""

from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Producto, VarianteProducto

MENSAJE_PRECIO = "El precio no puede ser negativo."
MENSAJE_PRECIO_INVALIDO = "El precio debe ser un número entero de pesos."
MENSAJE_DOS_PREDETERMINADAS = "Solo una variante puede ser la predeterminada del producto."
MENSAJE_PUBLICACION = (
    "Un producto publicado necesita al menos una variante activa "
    "y exactamente una variante predeterminada activa."
)
MENSAJE_NOMBRES = "Si el producto tiene varias variantes, cada una debe tener un nombre."
MENSAJE_NOMBRES_REPETIDOS = "Los nombres de las variantes no pueden repetirse en el mismo producto."
MENSAJE_PREDETERMINADA_ACTIVA = (
    "La variante predeterminada de un producto publicado tiene que estar activa."
)


def _precio(valor):
    """None o vacío es un precio pendiente. El cero es un precio confirmado."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return None
    try:
        convertido = Decimal(valor)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError(MENSAJE_PRECIO_INVALIDO) from exc
    if convertido < 0:
        raise ValidationError(MENSAJE_PRECIO)
    return convertido


def validar_variantes(variantes, producto_activo):
    errores = []
    predeterminadas = [variante for variante in variantes if variante.es_predeterminada]
    if len(predeterminadas) > 1:
        errores.append(MENSAJE_DOS_PREDETERMINADAS)
    if producto_activo:
        activas = [variante for variante in variantes if variante.activa]
        predeterminadas_activas = [variante for variante in activas if variante.es_predeterminada]
        if len(activas) < 1 or len(predeterminadas_activas) != 1:
            errores.append(MENSAJE_PUBLICACION)
    if len(variantes) > 1:
        vistos = set()
        falta_nombre = False
        repetido = False
        for variante in variantes:
            nombre = (variante.nombre or "").strip()
            if not nombre:
                falta_nombre = True
                continue
            clave = nombre.casefold()
            if clave in vistos:
                repetido = True
            vistos.add(clave)
        if falta_nombre:
            errores.append(MENSAJE_NOMBRES)
        if repetido:
            errores.append(MENSAJE_NOMBRES_REPETIDOS)
    if errores:
        raise ValidationError(errores)


def validar_producto_para_venta(producto):
    validar_variantes(list(producto.variantes.all()), producto.activo)


@transaction.atomic
def crear_producto_con_variante_inicial(
    *,
    categoria,
    nombre,
    slug,
    precio,
    descripcion="",
    referencia_imagen="",
    activo=True,
    nombre_variante="",
    orden_variante=0,
    precio_mayorista=None,
):
    precio = _precio(precio)
    precio_mayorista = _precio(precio_mayorista)
    producto = Producto(
        categoria=categoria,
        nombre=nombre,
        slug=slug,
        descripcion=descripcion,
        referencia_imagen=referencia_imagen,
        activo=activo,
    )
    producto.full_clean()
    producto.save()
    variante = VarianteProducto(
        producto=producto,
        nombre=(nombre_variante or "").strip(),
        precio=precio,
        precio_mayorista=precio_mayorista,
        es_predeterminada=True,
        activa=True,
        orden=orden_variante,
    )
    variante.full_clean()
    variante.save()
    validar_producto_para_venta(producto)
    return producto


@transaction.atomic
def agregar_variante(
    *,
    producto,
    nombre,
    precio,
    orden=0,
    activa=True,
    es_predeterminada=False,
    precio_mayorista=None,
):
    producto = Producto.objects.select_for_update().get(pk=producto.pk)
    variante = VarianteProducto(
        producto=producto,
        nombre=(nombre or "").strip(),
        precio=_precio(precio),
        precio_mayorista=_precio(precio_mayorista),
        orden=orden,
        activa=activa,
        es_predeterminada=False,
    )
    variante.full_clean()
    variante.save()
    if es_predeterminada:
        return cambiar_variante_predeterminada(variante)
    validar_producto_para_venta(producto)
    return variante


@transaction.atomic
def cambiar_variante_predeterminada(variante):
    variante = VarianteProducto.objects.select_for_update().get(pk=variante.pk)
    producto = Producto.objects.select_for_update().get(pk=variante.producto_id)
    if producto.activo and not variante.activa:
        raise ValidationError(MENSAJE_PREDETERMINADA_ACTIVA)
    anteriores = producto.variantes.select_for_update().filter(es_predeterminada=True).exclude(pk=variante.pk)
    for anterior in anteriores:
        anterior.es_predeterminada = False
        anterior.save(update_fields=["es_predeterminada"])
    variante.es_predeterminada = True
    variante.full_clean()
    variante.save()
    validar_producto_para_venta(producto)
    return variante


@transaction.atomic
def desactivar_variante(variante):
    variante = VarianteProducto.objects.select_for_update().get(pk=variante.pk)
    producto = Producto.objects.select_for_update().get(pk=variante.producto_id)
    if not variante.activa:
        return variante
    propuestas = []
    for actual in producto.variantes.select_for_update():
        if actual.pk == variante.pk:
            actual.activa = False
        propuestas.append(actual)
    validar_variantes(propuestas, producto.activo)
    variante.activa = False
    variante.save(update_fields=["activa"])
    return variante
