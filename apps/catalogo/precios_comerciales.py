"""Vista previa de precios del catálogo comercial.

Los montos salen de la transcripción revisada del libro
`Suspiro_Sureno_2_Catalogo_Actualizado.xlsx`, hoja CATALOGO REAL.
Esa hoja declara los precios como referencia y deja la vigencia pendiente.
Este módulo no crea productos ni variantes. La carga solo escribe las
coincidencias inequívocas y solo cuando se llama `aplicar_propuestas`.
El comando de gestión no la llama.
"""

from decimal import Decimal

from django.db import transaction

from .models import Producto

PROPUESTAS = (
    {
        "codigo": "C025",
        "slug": "pie-de-limon",
        "minorista": Decimal("13000"),
        "mayorista": None,
        "motivo": "La tarta entera coincide con el producto fotografiado. La porción es otro producto.",
    },
    {
        "codigo": "C050-C055",
        "slug": "rollitos-de-sabores",
        "minorista": Decimal("10500"),
        "mayorista": None,
        "motivo": "El producto es la caja de cuatro rollitos dulces, con hasta dos sabores. No es un rollo individual.",
    },
)

AMBIGUOS = (
    {"slug": "alfajor-brownie-con-relleno", "codigo": "C001", "motivo": "La fila agrupa varios centros y dos precios."},
    {"slug": "alfajor-cheesecake", "codigo": "C003", "motivo": "La fila agrupa varios centros y dos precios."},
    {"slug": "alfajor-manjar-brownie", "codigo": "C001", "motivo": "Se superpone con el brownie de manjar y no hay una fila exclusiva."},
    {"slug": "alfajor-manjar", "codigo": "C016", "motivo": "Hay varias filas de alfajor de manjar; no se confirma cuál es la fotografía."},
    {"slug": "berlines", "codigo": "C021", "motivo": "El precio es de una caja de cuatro. No se asigna al producto individual."},
    {"slug": "cheesecake-de-triton", "codigo": "C029", "motivo": "La fila agrupa Oreo y Tritón y pide confirmar la presentación."},
    {"slug": "kuchen-de-frutos-rojos", "codigo": "C028", "motivo": "La fila agrupa frambuesa y arándanos y pide confirmar la presentación."},
    {"slug": "porcion-cheesecake-oreo", "codigo": "C035", "motivo": "Comparte el bloque de porciones pendiente de confirmación."},
    {"slug": "porcion-cheesecake-triton", "codigo": "C035", "motivo": "Comparte el bloque de porciones pendiente de confirmación."},
    {"slug": "porcion-pie-de-limon", "codigo": "C033", "motivo": "La fila agrupa tres pies y el bloque pide confirmación."},
    {"slug": "porcion-pie-de-limon-frambuesa", "codigo": "C033", "motivo": "No tiene una fila de precio propia."},
    {"slug": "porcion-kuchen-de-frutos-rojos", "codigo": "C034", "motivo": "Comparte el bloque de porciones pendiente de confirmación."},
    {"slug": "porcion-torta-de-galleta", "codigo": "C038", "motivo": "El bloque de $2.300/$2.500 pide confirmar que aplica a galleta y yogurt."},
    {"slug": "porcion-torta-de-yogurt", "codigo": "C039", "motivo": "El bloque de $2.300/$2.500 pide confirmar que aplica a galleta y yogurt."},
    {"slug": "torta-de-bizcocho", "codigo": "C031", "motivo": "La fila comercial es una porción, no la torta entera."},
    {"slug": "torta-de-galleta", "codigo": "C038", "motivo": "La fila comercial es una porción, no la torta entera."},
    {"slug": "rollo-de-canela", "codigo": "C049", "motivo": "El precio es de una caja de cuatro. No se asigna al rollo individual."},
    {"slug": "rollo-de-frambuesa", "codigo": "C050", "motivo": "El precio es de la caja mixta, no del rollo individual."},
    {"slug": "rollo-oreo", "codigo": "C051", "motivo": "El precio es de la caja mixta, no del rollo individual."},
    {"slug": "rollo-de-manjar", "codigo": "C052", "motivo": "El precio es de la caja mixta, no del rollo individual."},
    {"slug": "rollo-de-limon", "codigo": "C053", "motivo": "El precio es de la caja mixta, no del rollo individual."},
    {"slug": "rollo-tiramisu", "codigo": "C054", "motivo": "El precio es de la caja mixta, no del rollo individual."},
    {"slug": "rollo-de-canela-y-manzana", "codigo": "C055", "motivo": "El precio es de la caja mixta, no del rollo individual."},
    {"slug": "rollo-de-ajo", "codigo": "C057", "motivo": "La fila es una caja y el rollo salado no entra en la caja dulce."},
    {"slug": "rollo-pizza", "codigo": "C056", "motivo": "La fila es una caja y el rollo salado no entra en la caja dulce."},
)

AUSENTES = (
    "Alfajor de maicena en paquete de cuatro",
    "Alfajores de manjaracuyá, membrillo, tiramisú, mate, naranjitas, cookies, avellana, pistacho y veganos",
    "Mantequillas de maní",
    "Pie de frambuesa, pie de maracuyá y tarta manjarate",
    "Porción de bizcocho, porción de torta amor, porción de tiramisú y porción de manjarate",
    "Productos mini y bombitas",
)

VARIANTES_NO_CREADAS = (
    {
        "codigo": "C049",
        "nombre": "Caja de 4 rollitos de canela",
        "minorista": Decimal("8500"),
        "motivo": "No existe un producto fotografiado de esa caja. No se crea la variante ni se usa el precio del rollo individual.",
    },
)


def revisar_propuestas():
    """Lee el catálogo y describe qué haría la carga. No escribe."""
    informe = []
    for propuesta in PROPUESTAS:
        producto = Producto.objects.filter(slug=propuesta["slug"]).first()
        if producto is None:
            informe.append({**propuesta, "estado": "producto ausente", "accion": "no se crea"})
            continue
        variante = producto.variantes.filter(es_predeterminada=True, activa=True).first()
        if variante is None or (variante.nombre or "").strip():
            informe.append({**propuesta, "estado": "presentación no confirmada", "accion": "omitida"})
            continue
        if variante.precio is not None:
            informe.append({**propuesta, "estado": "ya tiene precio minorista", "accion": "se conserva"})
            continue
        informe.append({**propuesta, "estado": "precio minorista vacío", "accion": "se podría cargar"})
    return informe


@transaction.atomic
def aplicar_propuestas(*, sobrescribir=False):
    """Escribe solo las propuestas inequívocas.

    No crea productos ni variantes. No pisa un precio minorista ya cargado
    salvo que `sobrescribir` sea verdadero. No borra un mayorista existente.
    """
    resultado = []
    for propuesta in PROPUESTAS:
        producto = Producto.objects.filter(slug=propuesta["slug"]).first()
        if producto is None:
            resultado.append({"slug": propuesta["slug"], "accion": "omitida"})
            continue
        variante = producto.variantes.select_for_update().filter(es_predeterminada=True, activa=True).first()
        if variante is None or (variante.nombre or "").strip():
            resultado.append({"slug": propuesta["slug"], "accion": "omitida"})
            continue
        if variante.precio is not None and not sobrescribir:
            resultado.append({"slug": propuesta["slug"], "accion": "conservada"})
            continue
        variante.precio = propuesta["minorista"]
        if propuesta["mayorista"] is not None and (variante.precio_mayorista is None or sobrescribir):
            variante.precio_mayorista = propuesta["mayorista"]
        variante.save(update_fields=["precio", "precio_mayorista"])
        resultado.append({"slug": propuesta["slug"], "accion": "cargada"})
    return resultado
