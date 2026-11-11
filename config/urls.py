from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.core.urls")),
    path("", include("apps.catalogo.urls")),
    path("", include("apps.cuentas.urls")),
    path("", include("apps.cuentas.api_urls")),
    path("", include("apps.cotizaciones.urls")),
    path("", include("apps.pedidos.urls")),
    path("", include("apps.inventario.urls")),
]

handler403 = "apps.cuentas.views.error_403"
