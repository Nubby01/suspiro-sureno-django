from django.urls import path

from .views import CatalogoPublicoView, ProductoDetalleView

# Sin namespace: la portada resuelve el nombre suelto "catalogo".
urlpatterns = [
    path("catalogo/", CatalogoPublicoView.as_view(), name="catalogo"),
    path("catalogo/<slug:slug>/", ProductoDetalleView.as_view(), name="producto_detalle"),
]
