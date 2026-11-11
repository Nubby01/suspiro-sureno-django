from django.urls import path

from apps.panel.catalogo_vistas import (
    GaleriaGestionView,
    ProductoEditarView,
    ProductoNuevoView,
    VariantesGestionView,
)
from apps.panel.views import (
    AlertasInventarioView,
    CatalogoInternoView,
    ClienteDetalleView,
    ClientesView,
    GestionView,
    PersonalView,
    TrabajoView,
)

from .views import CambiarClaveView, IngresoView, MiCuentaView, RegistroView, SalirView

# Sin namespace: los nombres quedan disponibles para el encabezado.
urlpatterns = [
    path("cuenta/gestion/alertas-stock/", AlertasInventarioView.as_view(), name="alertas_stock"),
    path("cuenta/registro/", RegistroView.as_view(), name="registro"),
    path("cuenta/ingresar/", IngresoView.as_view(), name="ingresar"),
    path("cuenta/salir/", SalirView.as_view(), name="salir"),
    path("cuenta/", MiCuentaView.as_view(), name="mi_cuenta"),
    path("cuenta/clave/", CambiarClaveView.as_view(), name="cambiar_clave"),
    path("cuenta/gestion/", GestionView.as_view(), name="gestion"),
    path("cuenta/gestion/catalogo/", CatalogoInternoView.as_view(), name="catalogo_interno"),
    path("cuenta/gestion/catalogo/nuevo/", ProductoNuevoView.as_view(), name="catalogo_nuevo"),
    path(
        "cuenta/gestion/catalogo/<int:producto_id>/",
        ProductoEditarView.as_view(),
        name="catalogo_editar",
    ),
    path(
        "cuenta/gestion/catalogo/<int:producto_id>/variantes/",
        VariantesGestionView.as_view(),
        name="catalogo_variantes",
    ),
    path(
        "cuenta/gestion/catalogo/<int:producto_id>/galeria/",
        GaleriaGestionView.as_view(),
        name="catalogo_galeria",
    ),
    path("cuenta/gestion/personal/", PersonalView.as_view(), name="personal"),
    path("cuenta/gestion/clientes/", ClientesView.as_view(), name="clientes_gestion"),
    path(
        "cuenta/gestion/clientes/<int:usuario_id>/",
        ClienteDetalleView.as_view(),
        name="cliente_detalle",
    ),
    path("cuenta/trabajo/", TrabajoView.as_view(), name="trabajo"),
]
