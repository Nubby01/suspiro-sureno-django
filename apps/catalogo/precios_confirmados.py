"""Carga de los precios minoristas confirmados.

Solo actualiza productos que ya existen y cuya presentación coincide.
No crea productos, no asigna precios de caja a rollos individuales
ambiguos y no modifica el precio mayorista.
"""

from decimal import Decimal

from django.db import transaction

from .berlines import PRESENTACION
from .models import Producto, VarianteProducto
from .servicios import agregar_variante, cambiar_variante_predeterminada

UNIDADES = {
    "alfajor-manjar": Decimal("2000"),
    "alfajor-cheesecake": Decimal("1800"),
    "alfajor-manjar-brownie": Decimal("2400"),
    "alfajor-brownie-con-relleno": Decimal("2400"),
    "porcion-torta-de-galleta": Decimal("2500"),
    "porcion-torta-de-yogurt": Decimal("2500"),
    "porcion-cheesecake-oreo": Decimal("3500"),
    "porcion-cheesecake-triton": Decimal("3500"),
    "porcion-pie-de-limon-frambuesa": Decimal("3500"),
    "porcion-kuchen-de-frutos-rojos": Decimal("3500"),
    "pie-de-limon": Decimal("13000"),
    "kuchen-de-frutos-rojos": Decimal("20000"),
    "cheesecake-de-triton": Decimal("25000"),
}

CAJAS = {
    "berlines": Decimal("5000"),
    "rollo-de-canela": Decimal("8500"),
    "rollitos-de-sabores": Decimal("10500"),
}

TAMANOS = {
    "torta-de-galleta": (
        ("10 personas", Decimal("15000")),
        ("15 personas", Decimal("20000")),
        ("20 personas", Decimal("25000")),
        ("25 personas", Decimal("28000")),
        ("30 personas", Decimal("32000")),
    ),
    "torta-de-bizcocho": (
        ("10 personas", Decimal("24000")),
        ("15 personas", Decimal("30000")),
        ("20 personas", Decimal("32000")),
        ("25 personas", Decimal("35000")),
        ("30 personas", Decimal("40000")),
    ),
}

PENDIENTES = (
    {
        "asunto": "Rollos por sabores individuales",
        "precio": Decimal("9000"),
        "motivo": (
            "No queda claro si ese precio es de cada rollo fotografiado o de otra caja "
            "distinta de Rollitos de sabores. Esos productos siguen sin precio."
        ),
    },
    {
        "asunto": "Rollos salados",
        "precio": Decimal("10500"),
        "motivo": (
            "Rollo de ajo y Rollo pizza son productos individuales. No existe una caja salada "
            "y no se mezcla con la caja dulce."
        ),
    },
    {
        "asunto": "Pie de frambuesa",
        "precio": Decimal("16000"),
        "motivo": "No existe el producto entero ni una fotografía propia. No se creó.",
    },
    {
        "asunto": "Cheesecake Oreo entero",
        "precio": Decimal("25000"),
        "motivo": (
            "No existe el producto. La fotografía static/imagenes/cheesecakedeoreocatalogo.png "
            "está disponible y no se asoció. La porción sigue siendo otro producto."
        ),
    },
    {
        "asunto": "Porción pie de limón",
        "precio": None,
        "motivo": "Esta lista no confirma un precio propio para esa porción.",
    },
)


def _activas(producto):
    return list(producto.variantes.select_for_update().filter(activa=True).order_by("orden", "id"))


def _guardar_precio(variante, precio, nombre=None):
    variante.precio = precio
    campos = ["precio"]
    if nombre is not None:
        variante.nombre = nombre
        campos.append("nombre")
    variante.full_clean()
    variante.save(update_fields=campos)


@transaction.atomic
def aplicar_precios_confirmados():
    """Escribe los precios confirmados. Se puede ejecutar más de una vez."""
    resultado = []
    for slug, precio in UNIDADES.items():
        producto = Producto.objects.select_for_update().filter(slug=slug).first()
        if producto is None:
            resultado.append({"slug": slug, "accion": "ausente"})
            continue
        activas = _activas(producto)
        if len(activas) != 1 or (activas[0].nombre or "").strip():
            resultado.append({"slug": slug, "accion": "omitida"})
            continue
        _guardar_precio(activas[0], precio)
        resultado.append({"slug": slug, "accion": "actualizada"})
    for slug, precio in CAJAS.items():
        producto = Producto.objects.select_for_update().filter(slug=slug).first()
        if producto is None:
            resultado.append({"slug": slug, "accion": "ausente"})
            continue
        activas = _activas(producto)
        if len(activas) != 1:
            resultado.append({"slug": slug, "accion": "omitida"})
            continue
        nombre = (activas[0].nombre or "").strip()
        if nombre not in ("", PRESENTACION):
            resultado.append({"slug": slug, "accion": "omitida"})
            continue
        _guardar_precio(activas[0], precio, PRESENTACION)
        resultado.append({"slug": slug, "accion": "actualizada"})
    for slug, tamanos in TAMANOS.items():
        producto = Producto.objects.select_for_update().filter(slug=slug).first()
        if producto is None:
            resultado.append({"slug": slug, "accion": "ausente"})
            continue
        resultado.append({"slug": slug, "accion": _aplicar_tamanos(producto, tamanos)})
    return resultado


def _aplicar_tamanos(producto, tamanos):
    existentes = {
        (variante.nombre or "").strip().casefold(): variante
        for variante in producto.variantes.select_for_update()
    }
    primero, precio_primero = tamanos[0]
    blanco = existentes.get("")
    if blanco is not None and blanco.activa and primero.casefold() in existentes:
        return "omitida"
    if blanco is not None and primero.casefold() not in existentes:
        _guardar_precio(blanco, precio_primero, primero)
        blanco.orden = 0
        blanco.activa = True
        blanco.save(update_fields=["orden", "activa"])
        existentes[primero.casefold()] = blanco
        existentes.pop("", None)
    for orden, (nombre, precio) in enumerate(tamanos):
        variante = existentes.get(nombre.casefold())
        if variante is None:
            variante = agregar_variante(
                producto=producto,
                nombre=nombre,
                precio=precio,
                orden=orden,
                activa=True,
                es_predeterminada=False,
            )
            existentes[nombre.casefold()] = variante
        else:
            variante.precio = precio
            variante.orden = orden
            variante.activa = True
            variante.full_clean()
            variante.save(update_fields=["precio", "orden", "activa"])
    predeterminada = VarianteProducto.objects.get(producto=producto, nombre=primero)
    if not predeterminada.es_predeterminada:
        cambiar_variante_predeterminada(predeterminada)
    return "actualizada"
