"""Presentación administrativa de recetas; no modifica el cálculo de consumos."""
from apps.catalogo.rollitos import SLUG as SLUG_ROLLITOS


def recetas_del_producto(producto):
    recetas = list(producto.recetas.select_related("variante").prefetch_related("ingredientes__insumo").order_by("pk"))
    filas = [{"receta": receta, "ingredientes": list(receta.ingredientes.all()),
              "demostracion": receta.alcance.startswith("ejemplo:")} for receta in recetas]
    comerciales = [fila for fila in filas if not fila["demostracion"]]
    general = next((fila for fila in comerciales if fila["receta"].variante_id is None), None)
    variantes = []
    for variante in producto.variantes.order_by("orden", "pk"):
        especifica = next((fila for fila in comerciales if fila["receta"].variante_id == variante.pk), None)
        fila = especifica if especifica is not None else general
        motivo = ""
        if producto.slug == SLUG_ROLLITOS:
            motivo = "Composición por sabores pendiente; no se aplica una receta única."
        elif fila is None:
            motivo = "No tiene receta comercial vinculada."
        elif not fila["ingredientes"]:
            motivo = "La receta vinculada aún no tiene ingredientes."
        elif fila["receta"].rendimiento <= 0:
            motivo = "El rendimiento debe ser mayor que cero."
        elif any(not ingrediente.insumo.activo for ingrediente in fila["ingredientes"]):
            motivo = "La receta contiene insumos inactivos."
        variantes.append({"variante": variante, "receta": fila["receta"] if fila else None,
                          "configurada": not motivo, "motivo": motivo,
                          "especifica": especifica is not None})
    return {"recetas_producto": filas, "variantes_receta": variantes,
            "receta_compuesta_pendiente": producto.slug == SLUG_ROLLITOS}
