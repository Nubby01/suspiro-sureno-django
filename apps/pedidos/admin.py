from django.contrib import admin

from .models import EventoPedido, LineaPedido, Pedido


class _SoloLectura(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class LineaPedidoInline(admin.TabularInline):
    model = LineaPedido
    extra = 0

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class EventoPedidoInline(admin.TabularInline):
    model = EventoPedido
    extra = 0

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Pedido)
class PedidoAdmin(_SoloLectura):
    list_display = ("codigo", "estado", "nombre", "total", "creada")
    list_filter = ("estado",)
    search_fields = ("codigo", "nombre")
    inlines = (LineaPedidoInline, EventoPedidoInline)
