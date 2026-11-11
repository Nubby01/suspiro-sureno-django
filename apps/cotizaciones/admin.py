from django.contrib import admin

from .models import Cotizacion, LineaCotizacion


class _SoloLectura(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class LineaCotizacionInline(admin.TabularInline):
    model = LineaCotizacion
    extra = 0

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Cotizacion)
class CotizacionAdmin(_SoloLectura):
    list_display = ("codigo", "estado", "nombre", "creada")
    list_filter = ("estado",)
    search_fields = ("codigo", "nombre")
    inlines = (LineaCotizacionInline,)


@admin.register(LineaCotizacion)
class LineaCotizacionAdmin(_SoloLectura):
    list_display = ("cotizacion", "nombre_producto", "cantidad", "precio_acordado")
