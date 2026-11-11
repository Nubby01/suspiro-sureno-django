from .servicios import destino_por_rol, etiqueta_por_rol


def cuenta(request):
    usuario = getattr(request, "user", None)
    if usuario is None or not usuario.is_authenticated:
        return {"destino_cuenta": "", "etiqueta_cuenta": ""}
    return {
        "destino_cuenta": destino_por_rol(usuario),
        "etiqueta_cuenta": etiqueta_por_rol(usuario),
    }
