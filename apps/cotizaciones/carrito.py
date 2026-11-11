"""Borrador de cotización guardado en la sesión. No guarda precios."""

CLAVE = "cotizacion_borrador"


def leer(request):
    crudo = request.session.get(CLAVE)
    if not isinstance(crudo, list):
        return []
    lineas = []
    for item in crudo:
        if not isinstance(item, dict):
            continue
        try:
            variante_id = int(item.get("variante_id"))
            cantidad = int(item.get("cantidad"))
        except (TypeError, ValueError):
            continue
        if not 1 <= cantidad <= 99:
            continue
        sabores = item.get("sabores") or []
        if not isinstance(sabores, list):
            sabores = []
        limpios = []
        for sabor in sabores[:2]:
            texto = str(sabor or "").strip()[:80]
            if texto and texto not in limpios:
                limpios.append(texto)
        lineas.append({"variante_id": variante_id, "cantidad": cantidad, "sabores": limpios})
    return lineas


def guardar(request, lineas):
    request.session[CLAVE] = lineas
    request.session.modified = True


def vaciar(request):
    request.session.pop(CLAVE, None)
    request.session.modified = True


def agregar(request, variante_id, cantidad, sabores):
    lineas = leer(request)
    for linea in lineas:
        if linea["variante_id"] == variante_id and linea["sabores"] == sabores:
            linea["cantidad"] = min(99, linea["cantidad"] + cantidad)
            guardar(request, lineas)
            return
    lineas.append({"variante_id": variante_id, "cantidad": cantidad, "sabores": sabores})
    guardar(request, lineas)


def actualizar(request, indice, cantidad):
    lineas = leer(request)
    if indice < 0 or indice >= len(lineas):
        raise IndexError
    if cantidad is None:
        lineas.pop(indice)
    else:
        lineas[indice]["cantidad"] = cantidad
    guardar(request, lineas)
