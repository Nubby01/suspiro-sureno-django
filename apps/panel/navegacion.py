"""Estructura visible de cada panel.

El trabajo asignado permite consultar los pedidos a cargo de cada ayudante.
"""

MODULOS_GESTION = (
    {"etiqueta": "Inicio", "disponible": True, "ruta": "gestion"},
    {"etiqueta": "Catálogo", "disponible": True, "ruta": "catalogo_interno"},
    {"etiqueta": "Cotizaciones", "disponible": True, "ruta": "cotizaciones_gestion"},
    {"etiqueta": "Pedidos", "disponible": True, "ruta": "pedidos_gestion"},
    {"etiqueta": "Inventario", "disponible": True, "ruta": "inventario_gestion"},
    {"etiqueta": "Producción", "disponible": True, "ruta": "produccion_gestion"},
    {"etiqueta": "Clientes", "disponible": True, "ruta": "clientes_gestion"},
    {"etiqueta": "Personal", "disponible": True, "ruta": "personal"},
    {"etiqueta": "Mi cuenta", "disponible": True, "ruta": "mi_cuenta"},
)

MODULOS_TRABAJO = (
    {"etiqueta": "Inicio", "disponible": True, "ruta": "trabajo"},
    {"etiqueta": "Trabajo asignado", "disponible": True, "ruta": "trabajo_asignado"},
    {"etiqueta": "Producción", "disponible": True, "ruta": "produccion_trabajo"},
    {"etiqueta": "Mi cuenta", "disponible": True, "ruta": "mi_cuenta"},
)

PANELES = {
    "gestion": {
        "ruta": "gestion",
        "kicker": "Gestión",
        "titulo": "Área de administración",
        "introduccion": "Desde aquí administras el catálogo, los pedidos y el taller.",
        "modulos": MODULOS_GESTION,
    },
    "trabajo": {
        "ruta": "trabajo",
        "kicker": "Trabajo",
        "titulo": "Área de trabajo",
        "introduccion": "Desde aquí revisas la producción disponible.",
        "modulos": MODULOS_TRABAJO,
    },
}


def contexto_panel(clave):
    return PANELES[clave]


def seccion_activa(nombre):
    grupos = {
        "cotizaciones_gestion": ("cotizaciones_gestion", "cotizacion_gestion", "cotizacion_pdf_gestion"),
        "pedidos_gestion": ("pedidos_gestion", "pedido_gestion"),
        "inventario_gestion": ("inventario_gestion", "inventario_ficha", "inventario_nuevo", "inventario_editar", "inventario_entrada", "inventario_ajuste", "inventario_movimientos", "inventario_consumos", "inventario_recetas", "inventario_receta_nueva", "inventario_receta_editar"),
        "produccion_gestion": ("produccion_gestion", "produccion_gestion_detalle"),
        "produccion_trabajo": ("produccion_trabajo", "produccion_trabajo_detalle"),
        "clientes_gestion": ("clientes_gestion", "cliente_detalle"),
        "catalogo_interno": ("catalogo_interno", "catalogo_nuevo", "catalogo_editar", "catalogo_variantes", "catalogo_galeria"),
    }
    for seccion, rutas in grupos.items():
        if nombre in rutas:
            return seccion
    return nombre
