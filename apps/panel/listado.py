"""Listado interno de productos. Esta consulta no crea ni modifica filas."""

from django.db.models import Prefetch

from apps.catalogo.consultas import formato_clp
from apps.catalogo.imagenes import fotografia_publica
from apps.catalogo.models import Categoria, Producto, VarianteProducto


def listado_interno(*, busqueda="", categoria="", request=None):
    texto = " ".join((busqueda or "").split())[:120]
    slug = (categoria or "").strip()[:80]
    consulta = (
        Producto.objects.select_related("categoria")
        .prefetch_related(
            Prefetch(
                "variantes",
                queryset=VarianteProducto.objects.order_by("orden", "id"),
            )
        )
        .order_by("categoria__orden", "categoria__nombre", "nombre", "id")
    )
    if request is not None:
        from .demostracion import filtro_demo
        consulta = filtro_demo(consulta, request)
    if texto:
        consulta = consulta.filter(nombre__icontains=texto)
    if slug:
        consulta = consulta.filter(categoria__slug=slug)
    filas = [_fila(producto) for producto in consulta]
    return {
        "filas": filas,
        "total": len(filas),
        "busqueda": texto,
        "categoria_activa": slug,
        "categorias": list(Categoria.objects.order_by("orden", "nombre", "id")),
        "hay_filtro": bool(texto or slug),
    }


def _fila(producto):
    predeterminada = next(
        (variante for variante in producto.variantes.all() if variante.es_predeterminada),
        None,
    )
    if predeterminada is None:
        precio_texto = "Sin variante predeterminada"
        precio_pendiente = False
    elif predeterminada.precio is None:
        precio_texto = "Consultar precio"
        precio_pendiente = True
    else:
        precio_texto = formato_clp(predeterminada.precio)
        precio_pendiente = False
    foto = fotografia_publica(producto.referencia_imagen, producto.nombre)
    return {
        "id": producto.pk,
        "nombre": producto.nombre,
        "categoria": producto.categoria.nombre,
        "activo": producto.activo,
        "estado": "Activo" if producto.activo else "Inactivo",
        "precio_texto": precio_texto,
        "precio_pendiente": precio_pendiente,
        "imagen": foto["imagen"],
        "imagen_alt": foto["imagen_alt"],
        "imagen_ancho": foto["imagen_ancho"],
        "imagen_alto": foto["imagen_alto"],
    }
