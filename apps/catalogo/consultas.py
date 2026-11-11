"""Consultas del catálogo público.

`referencia_imagen` guarda una ruta relativa a una sola copia estática,
con el formato documentado en `imagenes.py`. Si está vacía o no es segura,
la ficha conserva el recuadro «Fotografía pendiente».
"""

from decimal import Decimal

from django.db.models import Count, Prefetch
from django.urls import reverse

from .cajas import NOTAS as NOTAS_CAJA
from .berlines import SABORES as SABORES_BERLIN
from .berlines import SLUG as SLUG_BERLIN
from .brownie import NOMBRES as CENTROS_BROWNIE
from .brownie import SLUG as SLUG_BROWNIE
from .imagenes import fotografia_publica
from .models import Producto, VarianteProducto


PERSONAS = ("torta-de-galleta", "torta-de-bizcocho")


def sabores_brownie(producto):
    if producto.slug != SLUG_BROWNIE:
        return []
    return [{"codigo": codigo, "nombre": nombre} for codigo, nombre in CENTROS_BROWNIE.items()]


def sabores_berlines(producto):
    if producto.slug != SLUG_BERLIN:
        return []
    return [{"codigo": codigo, "nombre": nombre} for codigo, nombre in SABORES_BERLIN]


def formato_clp(valor):
    entero = int(Decimal(valor))
    return "$" + f"{entero:,}".replace(",", ".")


def productos_publicos():
    """Productos activos, de categorías activas, con al menos una variante activa."""
    vendibles = VarianteProducto.objects.filter(activa=True).values("producto_id")
    variantes_activas = VarianteProducto.objects.filter(activa=True).order_by("orden", "id")
    return (
        Producto.objects.filter(activo=True, categoria__activa=True, pk__in=vendibles)
        .select_related("categoria")
        .prefetch_related(
            Prefetch("variantes", queryset=variantes_activas, to_attr="variantes_publicas")
        )
        .annotate(total_galeria=Count("galeria"))
        .order_by("categoria__orden", "categoria__nombre", "nombre", "id")
    )


def _presentar_variante(variante, nombre_producto):
    nombre = (variante.nombre or "").strip()
    pendiente = variante.precio is None
    return {
        "id": variante.pk,
        "nombre": nombre,
        "etiqueta": nombre or nombre_producto,
        "precio": None if pendiente else int(variante.precio),
        "precio_texto": "Consultar precio" if pendiente else formato_clp(variante.precio),
        "precio_pendiente": pendiente,
        "es_predeterminada": variante.es_predeterminada,
    }


def catalogo_publico():
    grupos = []
    indice = {}
    for producto in productos_publicos():
        variantes = [
            _presentar_variante(variante, producto.nombre)
            for variante in producto.variantes_publicas
        ]
        if not variantes:
            continue
        inicial = next(
            (variante for variante in variantes if variante["es_predeterminada"]),
            variantes[0],
        )
        categoria = producto.categoria
        grupo = indice.get(categoria.pk)
        if grupo is None:
            grupo = {
                "id": f"categoria-{categoria.slug}",
                "slug": categoria.slug,
                "nombre": categoria.nombre,
                "descripcion": categoria.descripcion,
                "productos": [],
            }
            indice[categoria.pk] = grupo
            grupos.append(grupo)
        galeria = sabores_publicos(producto) if producto.total_galeria else []
        busqueda = " ".join(
            parte
            for parte in [
                producto.nombre,
                categoria.nombre,
                (producto.descripcion or "").strip(),
                *(variante["etiqueta"] for variante in variantes),
                *(sabor["nombre"] for sabor in galeria),
                *(sabor["nombre"] for sabor in sabores_berlines(producto)),
            ]
            if parte
        )
        ficha = {
            "id": producto.pk,
            "nombre": producto.nombre,
            "slug": producto.slug,
            "descripcion": (producto.descripcion or "").strip(),
            "variantes": variantes,
            "inicial": inicial,
            "selector": len(variantes) > 1,
            "variante_unica": variantes[0]["nombre"] if len(variantes) == 1 else "",
            "personas": producto.slug in PERSONAS,
            "nota_caja": NOTAS_CAJA.get(producto.slug, ""),
            "sabores_caja": _opciones_caja(producto),
            "sabores_berlines": sabores_berlines(producto),
            "sabores_brownie": sabores_brownie(producto),
            "galeria": galeria,
            "busqueda": busqueda,
        }
        if ficha["sabores_brownie"]:
            ficha["busqueda"] = busqueda + " " + " ".join(
                sabor["nombre"] for sabor in ficha["sabores_brownie"]
            )
        ficha.update(fotografia_publica(producto.referencia_imagen, producto.nombre))
        ficha["imagen_diferida"] = not (len(grupos) == 1 and not grupo["productos"])
        ficha["detalle"] = (
            reverse("producto_detalle", kwargs={"slug": producto.slug})
            if producto.total_galeria
            else ""
        )
        grupo["productos"].append(ficha)
    return {"grupos": grupos, "hay_productos": bool(grupos)}


def sabores_publicos(producto):
    """Fotografías de la galería, sin precios de cada sabor."""
    elementos = producto.galeria.select_related("producto_origen").order_by("orden", "id")
    sabores = []
    for elemento in elementos:
        origen = elemento.producto_origen
        nombre = (elemento.nombre or (origen.nombre if origen else "")).strip()
        referencia = (elemento.referencia_imagen or (origen.referencia_imagen if origen else "")).strip()
        if not nombre:
            continue
        sabor = {"nombre": nombre, "slug": origen.slug if origen else ""}
        sabor.update(fotografia_publica(referencia, nombre))
        sabores.append(sabor)
    return sabores


def _opciones_caja(producto):
    if producto.slug != "rollitos-de-sabores":
        return []
    opciones = []
    for elemento in producto.galeria.select_related("producto_origen").order_by("orden", "id"):
        origen = elemento.producto_origen
        if origen and origen.activo:
            opciones.append({"slug": origen.slug, "nombre": origen.nombre})
    return opciones


def detalle_publico(slug):
    producto = productos_publicos().filter(slug=slug).first()
    if producto is None:
        return None
    variantes = [
        _presentar_variante(variante, producto.nombre)
        for variante in producto.variantes_publicas
    ]
    if not variantes:
        return None
    inicial = next(
        (variante for variante in variantes if variante["es_predeterminada"]),
        variantes[0],
    )
    sabores = sabores_publicos(producto)
    ficha = {
        "id": producto.pk,
        "nombre": producto.nombre,
        "slug": producto.slug,
        "descripcion": (producto.descripcion or "").strip(),
        "categoria": producto.categoria.nombre,
        "categoria_slug": producto.categoria.slug,
        "inicial": inicial,
        "variantes": variantes,
        "selector": len(variantes) > 1,
        "variante_unica": variantes[0]["nombre"] if len(variantes) == 1 else "",
        "personas": producto.slug in PERSONAS,
        "nota_caja": NOTAS_CAJA.get(producto.slug, ""),
        "sabores_caja": _opciones_caja(producto),
        "sabores_berlines": sabores_berlines(producto),
        "sabores_brownie": sabores_brownie(producto),
    }
    ficha.update(fotografia_publica(producto.referencia_imagen, producto.nombre))
    return {"producto": ficha, "sabores": sabores}
