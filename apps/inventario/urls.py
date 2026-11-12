from django.urls import path

from .views import (
    FichaInsumoView,
    AjusteView,
    EntradaView,
    InsumoEditarView,
    InsumoNuevoView,
    ListaInsumosView,
    MovimientosView,
    ProduccionGestionDetalleView,
    ProduccionGestionView,
    ProduccionTrabajoDetalleView,
    ProduccionTrabajoView,
    RecetaNuevaView,
    RecetaEditarView,
    RecetasView,
    ReporteConsumosView,
)

urlpatterns = [
    path("cuenta/gestion/inventario/consumos/", ReporteConsumosView.as_view(), name="inventario_consumos"),
    path("cuenta/gestion/inventario/recetas/<int:receta_id>/", RecetaEditarView.as_view(), name="inventario_receta_editar"),
    path("cuenta/gestion/inventario/<int:insumo_id>/historial/", FichaInsumoView.as_view(), name="inventario_ficha"),
    path("cuenta/trabajo/asignado/", ProduccionTrabajoView.as_view(), name="trabajo_asignado"),
    path("cuenta/gestion/inventario/", ListaInsumosView.as_view(), name="inventario_gestion"),
    path("cuenta/gestion/inventario/nuevo/", InsumoNuevoView.as_view(), name="inventario_nuevo"),
    path("cuenta/gestion/inventario/<int:insumo_id>/", InsumoEditarView.as_view(), name="inventario_editar"),
    path("cuenta/gestion/inventario/entradas/", EntradaView.as_view(), name="inventario_entrada"),
    path("cuenta/gestion/inventario/ajustes/", AjusteView.as_view(), name="inventario_ajuste"),
    path("cuenta/gestion/inventario/movimientos/", MovimientosView.as_view(), name="inventario_movimientos"),
    path("cuenta/gestion/inventario/recetas/", RecetasView.as_view(), name="inventario_recetas"),
    path("cuenta/gestion/inventario/recetas/nueva/", RecetaNuevaView.as_view(), name="inventario_receta_nueva"),
    path("cuenta/gestion/produccion/", ProduccionGestionView.as_view(), name="produccion_gestion"),
    path(
        "cuenta/gestion/produccion/<str:codigo>/",
        ProduccionGestionDetalleView.as_view(),
        name="produccion_gestion_detalle",
    ),
    path("cuenta/trabajo/produccion/", ProduccionTrabajoView.as_view(), name="produccion_trabajo"),
    path(
        "cuenta/trabajo/produccion/<str:codigo>/",
        ProduccionTrabajoDetalleView.as_view(),
        name="produccion_trabajo_detalle",
    ),
]
