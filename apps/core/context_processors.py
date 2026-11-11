from .negocio import datos_publicos
from .presentacion import enlaces_disponibles


def navegacion(request):
    nombre = getattr(getattr(request, "resolver_match", None), "url_name", "") or ""
    from apps.panel.navegacion import seccion_activa
    from apps.cotizaciones.carrito import leer
    from apps.catalogo.models import VarianteProducto
    lineas = leer(request) if hasattr(request, "session") else []
    validas = set(VarianteProducto.objects.filter(pk__in=[x["variante_id"] for x in lineas], activa=True, producto__activo=True, producto__categoria__activa=True).values_list("pk", flat=True)) if lineas else set()
    seleccionadas = [x for x in lineas if x["variante_id"] in validas]
    contador = sum(x["cantidad"] for x in seleccionadas)
    from apps.cuentas.models import Usuario
    usuario = getattr(request, "user", None)
    demo_filtro = bool(usuario and usuario.is_authenticated and (usuario.is_superuser or usuario.rol == Usuario.Rol.ADMINISTRADORA) and nombre in ("cotizaciones_gestion", "pedidos_gestion", "inventario_gestion", "produccion_gestion", "catalogo_interno", "clientes_gestion", "personal"))
    alertas_inventario = None
    if usuario and usuario.is_authenticated and (usuario.is_superuser or usuario.rol == Usuario.Rol.ADMINISTRADORA):
        from apps.panel.alertas import insumos_con_alerta
        alertas_inventario = insumos_con_alerta()
    return {"alertas_inventario": alertas_inventario, "enlaces_nav": enlaces_disponibles(), "negocio": datos_publicos(), "seccion_panel": seccion_activa(nombre), "contador_cotizacion": contador, "lineas_cotizacion": len(seleccionadas), "demo_filtro": demo_filtro, "incluir_demo": request.GET.get("incluir_demo") == "1"}
