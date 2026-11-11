"""Presentaciones de caja que todavía no tenían precio.

No modifica un precio ya cargado. La caja de canela y la caja combinada
quedan fuera de esta carga.
"""

from decimal import Decimal

from django.db import transaction

from .models import Producto

PRESENTACION = "Caja de 4"

NOTAS = {
    "rollo-de-canela": "Caja de 4. Los cuatro rollitos son de canela.",
    "rollo-de-frambuesa": "Caja de 4. Los cuatro rollitos son de este sabor.",
    "rollo-oreo": "Caja de 4. Los cuatro rollitos son de este sabor.",
    "rollo-de-manjar": "Caja de 4. Los cuatro rollitos son de este sabor.",
    "rollo-de-limon": "Caja de 4. Los cuatro rollitos son de este sabor.",
    "rollo-tiramisu": "Caja de 4. Los cuatro rollitos son de este sabor.",
    "rollo-de-canela-y-manzana": "Caja de 4. Los cuatro rollitos son de este sabor.",
    "rollo-de-ajo": "Caja de 4 salada. No se mezcla con sabores dulces.",
    "rollo-pizza": "Caja de 4 salada. No se mezcla con sabores dulces.",
}

PRECIOS_NUEVOS = {
    "rollo-de-frambuesa": Decimal("9000"),
    "rollo-oreo": Decimal("9000"),
    "rollo-de-manjar": Decimal("9000"),
    "rollo-de-limon": Decimal("9000"),
    "rollo-tiramisu": Decimal("9000"),
    "rollo-de-canela-y-manzana": Decimal("9000"),
    "rollo-de-ajo": Decimal("10500"),
    "rollo-pizza": Decimal("10500"),
}


@transaction.atomic
def aplicar_cajas_faltantes():
    """Completa solo variantes sin precio. No pisa valores existentes."""
    resultado = []
    for slug, precio in PRECIOS_NUEVOS.items():
        producto = Producto.objects.select_for_update().filter(slug=slug).first()
        if producto is None:
            resultado.append({"slug": slug, "accion": "ausente"})
            continue
        activas = list(producto.variantes.select_for_update().filter(activa=True))
        if len(activas) != 1:
            resultado.append({"slug": slug, "accion": "omitida"})
            continue
        variante = activas[0]
        nombre = (variante.nombre or "").strip()
        if variante.precio is not None or nombre not in ("", PRESENTACION):
            resultado.append({"slug": slug, "accion": "conservada"})
            continue
        variante.nombre = PRESENTACION
        variante.precio = precio
        variante.full_clean()
        variante.save(update_fields=["nombre", "precio"])
        resultado.append({"slug": slug, "accion": "actualizada"})
    return resultado
