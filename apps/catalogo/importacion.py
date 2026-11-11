"""Carga reproducible de los 26 productos con fotografía.

Los nombres son los propuestos en la preparación del catálogo y siguen
sujetos a revisión. No incluye precios del catálogo comercial.
"""

from django.db import transaction

from .imagenes import referencia_es_segura, ruta_fisica
from .models import Categoria, Producto
from .servicios import crear_producto_con_variante_inicial

CATEGORIAS = (
    {"nombre": "Alfajores", "slug": "alfajores", "orden": 1},
    {"nombre": "Rollos dulces", "slug": "rollos-dulces", "orden": 2},
    {"nombre": "Rollos salados", "slug": "rollos-salados", "orden": 3},
    {"nombre": "Tortas", "slug": "tortas", "orden": 4},
    {"nombre": "Cheesecakes", "slug": "cheesecakes", "orden": 5},
    {"nombre": "Pies y kuchenes", "slug": "pies-y-kuchenes", "orden": 6},
    {"nombre": "Otros dulces", "slug": "otros-dulces", "orden": 7},
)

MANIFIESTO = (
    {"nombre": "Alfajor brownie con relleno", "slug": "alfajor-brownie-con-relleno", "categoria": "alfajores", "referencia_imagen": "imagenes/catalogo-web/alfajorbrownieconrellenocatalogo.jpg"},
    {"nombre": "Alfajor cheesecake", "slug": "alfajor-cheesecake", "categoria": "alfajores", "referencia_imagen": "imagenes/catalogo-web/alfajorcheesecakecatalogo.jpg"},
    {"nombre": "Alfajor manjar brownie", "slug": "alfajor-manjar-brownie", "categoria": "alfajores", "referencia_imagen": "imagenes/catalogo-web/alfajormanjarbrowniecatalogo.jpg"},
    {"nombre": "Alfajor manjar", "slug": "alfajor-manjar", "categoria": "alfajores", "referencia_imagen": "imagenes/catalogo-web/alfajormanjarcatalogo.jpg"},
    {"nombre": "Berlines", "slug": "berlines", "categoria": "otros-dulces", "referencia_imagen": "imagenes/catalogo-web/berlinescatalogo.jpg"},
    {"nombre": "Cheesecake de Tritón", "slug": "cheesecake-de-triton", "categoria": "cheesecakes", "referencia_imagen": "imagenes/catalogo-web/cheesecakedetritoncatalogo.jpg"},
    {"nombre": "Kuchen de frutos rojos", "slug": "kuchen-de-frutos-rojos", "categoria": "pies-y-kuchenes", "referencia_imagen": "imagenes/catalogo-web/kuchenfrutosrojoscatalogo.jpg"},
    {"nombre": "Pie de limón", "slug": "pie-de-limon", "categoria": "pies-y-kuchenes", "referencia_imagen": "imagenes/catalogo-web/piedelimoncatalogo.jpg"},
    {"nombre": "Porción cheesecake Oreo", "slug": "porcion-cheesecake-oreo", "categoria": "cheesecakes", "referencia_imagen": "imagenes/catalogo-web/porcioncheesecakeoreocatalogo.jpg"},
    {"nombre": "Porción cheesecake Tritón", "slug": "porcion-cheesecake-triton", "categoria": "cheesecakes", "referencia_imagen": "imagenes/catalogo-web/porcioncheesecaketritoncatalogo.jpg"},
    {"nombre": "Porción kuchen de frutos rojos", "slug": "porcion-kuchen-de-frutos-rojos", "categoria": "pies-y-kuchenes", "referencia_imagen": "imagenes/catalogo-web/porcionkuchendefrutosrojoscatalogo.jpg"},
    {"nombre": "Porción pie de limón", "slug": "porcion-pie-de-limon", "categoria": "pies-y-kuchenes", "referencia_imagen": "imagenes/catalogo-web/porcionpiedelimoncatalogo.jpg"},
    {"nombre": "Porción pie de limón frambuesa", "slug": "porcion-pie-de-limon-frambuesa", "categoria": "pies-y-kuchenes", "referencia_imagen": "imagenes/catalogo-web/porcionpiedelimonframbuesacatalogo.jpg"},
    {"nombre": "Porción torta de galleta", "slug": "porcion-torta-de-galleta", "categoria": "tortas", "referencia_imagen": "imagenes/catalogo-web/porciontortagalletacatalogo.jpg"},
    {"nombre": "Porción torta de yogurt", "slug": "porcion-torta-de-yogurt", "categoria": "tortas", "referencia_imagen": "imagenes/catalogo-web/porciontortayogurtcatalogo.jpg"},
    {"nombre": "Rollo de ajo", "slug": "rollo-de-ajo", "categoria": "rollos-salados", "referencia_imagen": "imagenes/catalogo-web/rolloajocatalogo.jpg"},
    {"nombre": "Rollo de canela y manzana", "slug": "rollo-de-canela-y-manzana", "categoria": "rollos-dulces", "referencia_imagen": "imagenes/catalogo-web/rollocanelamanzanacatalogo.jpg"},
    {"nombre": "Rollo de canela", "slug": "rollo-de-canela", "categoria": "rollos-dulces", "referencia_imagen": "imagenes/catalogo-web/rollodecanelacatalogo.jpg"},
    {"nombre": "Rollo de frambuesa", "slug": "rollo-de-frambuesa", "categoria": "rollos-dulces", "referencia_imagen": "imagenes/catalogo-web/rollodeframbuesacatalogo.jpg"},
    {"nombre": "Rollo de limón", "slug": "rollo-de-limon", "categoria": "rollos-dulces", "referencia_imagen": "imagenes/catalogo-web/rollolimoncatalogo.jpg"},
    {"nombre": "Rollo de manjar", "slug": "rollo-de-manjar", "categoria": "rollos-dulces", "referencia_imagen": "imagenes/catalogo-web/rollomanjarcatalogo.jpg"},
    {"nombre": "Rollo Oreo", "slug": "rollo-oreo", "categoria": "rollos-dulces", "referencia_imagen": "imagenes/catalogo-web/rollooreocatalogo.jpg"},
    {"nombre": "Rollo pizza", "slug": "rollo-pizza", "categoria": "rollos-salados", "referencia_imagen": "imagenes/catalogo-web/rollopizzacatalogo.jpg"},
    {"nombre": "Rollo tiramisú", "slug": "rollo-tiramisu", "categoria": "rollos-dulces", "referencia_imagen": "imagenes/catalogo-web/rollotiramisucatalogo.jpg"},
    {"nombre": "Torta de bizcocho", "slug": "torta-de-bizcocho", "categoria": "tortas", "referencia_imagen": "imagenes/catalogo-web/tortabizcochocatalogo.jpg"},
    {"nombre": "Torta de galleta", "slug": "torta-de-galleta", "categoria": "tortas", "referencia_imagen": "imagenes/catalogo-web/tortadegalletacatalogo.jpg"},
)


class ErrorImportacion(Exception):
    def __init__(self, mensajes):
        if isinstance(mensajes, str):
            mensajes = [mensajes]
        self.mensajes = list(mensajes)
        super().__init__("\n".join(self.mensajes))


def validar_estructura(productos, categorias):
    errores = []
    if len(categorias) != 7:
        errores.append("El manifiesto debe definir exactamente 7 categorías.")
    if len(productos) != 26:
        errores.append("El manifiesto debe definir exactamente 26 productos.")
    slugs_categoria = [categoria["slug"] for categoria in categorias]
    if len(slugs_categoria) != len(set(slugs_categoria)):
        errores.append("Hay slugs de categoría repetidos en el manifiesto.")
    slugs = [producto["slug"] for producto in productos]
    if len(slugs) != len(set(slugs)):
        errores.append("Hay slugs de producto repetidos en el manifiesto.")
    fotos = [producto["referencia_imagen"] for producto in productos]
    if len(fotos) != len(set(fotos)):
        errores.append("Hay fotografías repetidas en el manifiesto.")
    conocidas = set(slugs_categoria)
    for producto in productos:
        if producto["categoria"] not in conocidas:
            errores.append(
                f"El producto {producto['slug']} usa una categoría que no está en el manifiesto."
            )
        if not referencia_es_segura(producto["referencia_imagen"]):
            errores.append(
                f"La ruta de {producto['slug']} no es una referencia segura de catálogo."
            )
    return errores


def validar_imagenes(productos):
    errores = []
    for producto in productos:
        if ruta_fisica(producto["referencia_imagen"]) is None:
            errores.append(
                f"No está la fotografía de {producto['slug']}: {producto['referencia_imagen']}"
            )
    return errores


def _producto_compatible(producto, item):
    if producto.nombre != item["nombre"]:
        return "el nombre no coincide"
    if producto.categoria.slug != item["categoria"]:
        return "la categoría no coincide"
    if producto.referencia_imagen != item["referencia_imagen"]:
        return "la fotografía no coincide"
    if (producto.descripcion or "") != "":
        return "ya tiene una descripción"
    if not producto.activo:
        return "está inactivo"
    variantes = list(producto.variantes.all())
    if len(variantes) != 1:
        return "no tiene exactamente una variante"
    variante = variantes[0]
    if (variante.nombre or "") != "":
        return "la variante inicial tiene nombre"
    if variante.precio is not None:
        return "la variante ya tiene un precio"
    if not variante.activa or not variante.es_predeterminada:
        return "la variante inicial no está activa y predeterminada"
    return ""


def planificar(productos, categorias):
    """Lee la base y describe la carga. No guarda nada."""
    errores = []
    categorias_nuevas = []
    categorias_reutilizadas = []
    for categoria in categorias:
        existente = Categoria.objects.filter(slug=categoria["slug"]).first()
        if existente is None:
            categorias_nuevas.append(categoria["slug"])
            continue
        if existente.nombre != categoria["nombre"]:
            errores.append(
                f"La categoría {categoria['slug']} ya existe con el nombre «{existente.nombre}»."
            )
        elif not existente.activa:
            errores.append(f"La categoría {categoria['slug']} ya existe, pero está inactiva.")
        else:
            categorias_reutilizadas.append(categoria["slug"])
    productos_nuevos = []
    productos_compatibles = []
    for item in productos:
        existente = Producto.objects.filter(slug=item["slug"]).select_related("categoria").first()
        if existente is None:
            productos_nuevos.append(item["slug"])
            continue
        motivo = _producto_compatible(existente, item)
        if motivo:
            errores.append(f"El producto {item['slug']} ya existe y {motivo}.")
        else:
            productos_compatibles.append(item["slug"])
    if errores:
        raise ErrorImportacion(errores)
    return {
        "categorias_nuevas": categorias_nuevas,
        "categorias_reutilizadas": categorias_reutilizadas,
        "productos_nuevos": productos_nuevos,
        "productos_compatibles": productos_compatibles,
    }


def _aplicar(productos, categorias):
    guardadas = {}
    for categoria in categorias:
        existente = Categoria.objects.filter(slug=categoria["slug"]).first()
        if existente is None:
            existente = Categoria(
                nombre=categoria["nombre"],
                slug=categoria["slug"],
                orden=categoria["orden"],
                descripcion="",
                activa=True,
            )
            existente.full_clean()
            existente.save()
        guardadas[categoria["slug"]] = existente
    for item in productos:
        if Producto.objects.filter(slug=item["slug"]).exists():
            continue
        crear_producto_con_variante_inicial(
            categoria=guardadas[item["categoria"]],
            nombre=item["nombre"],
            slug=item["slug"],
            precio=None,
            descripcion="",
            referencia_imagen=item["referencia_imagen"],
            activo=True,
            nombre_variante="",
        )


def importar_catalogo(*, dry_run=False):
    errores = validar_estructura(MANIFIESTO, CATEGORIAS)
    errores.extend(validar_imagenes(MANIFIESTO))
    if errores:
        raise ErrorImportacion(errores)
    if dry_run:
        return planificar(MANIFIESTO, CATEGORIAS)
    with transaction.atomic():
        plan = planificar(MANIFIESTO, CATEGORIAS)
        _aplicar(MANIFIESTO, CATEGORIAS)
        return plan
