from django.urls import path

from .views import (
    AgregarCotizacionView,
    ConsultaCotizacionView,
    DetalleGestionView,
    ListaGestionView,
    MisCotizacionesView,
    PdfCotizacionView,
    PdfGestionView,
    SolicitudView,
)

urlpatterns = [
    path("cotizacion/", SolicitudView.as_view(), name="cotizaciones"),
    path("cotizacion/agregar/", AgregarCotizacionView.as_view(), name="cotizacion_agregar"),
    path("cotizacion/<str:token>/", ConsultaCotizacionView.as_view(), name="cotizacion_consulta"),
    path("cotizacion/<str:token>/pdf/", PdfCotizacionView.as_view(), name="cotizacion_pdf"),
    path("cuenta/cotizaciones/", MisCotizacionesView.as_view(), name="mis_cotizaciones"),
    path("cuenta/gestion/cotizaciones/", ListaGestionView.as_view(), name="cotizaciones_gestion"),
    path(
        "cuenta/gestion/cotizaciones/<str:codigo>/",
        DetalleGestionView.as_view(),
        name="cotizacion_gestion",
    ),
    path(
        "cuenta/gestion/cotizaciones/<str:codigo>/pdf/",
        PdfGestionView.as_view(),
        name="cotizacion_pdf_gestion",
    ),
]
