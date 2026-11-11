import secrets

from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError

from .models import ConsumoPedido, Insumo, MovimientoInventario, Receta, RecetaIngrediente
from .servicios import MENSAJE_EXISTENCIA, MENSAJE_INACTIVO, guardar_insumo, registrar_movimiento


class InsumoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "unidad", "existencia", "stock_minimo", "stock_critico", "activo", "actualizado")
    search_fields = ("nombre",)
    readonly_fields = ("existencia", "actualizado")
    fields = ("nombre", "unidad", "existencia", "stock_minimo", "stock_critico", "activo", "actualizado")

    def save_model(self, request, obj, form, change):
        guardar_insumo(
            insumo=obj,
            nombre=form.cleaned_data["nombre"],
            unidad=form.cleaned_data["unidad"],
            stock_minimo=form.cleaned_data["stock_minimo"],
            stock_critico=form.cleaned_data.get("stock_critico"),
            activo=form.cleaned_data["activo"],
        )

    def has_delete_permission(self, request, obj=None):
        if obj is None:
            return False
        return not obj.movimientos.exists() and not obj.ingredientes.exists()


class FormularioMovimiento(forms.ModelForm):
    clave_solicitud = forms.CharField(widget=forms.HiddenInput)

    class Meta:
        model = MovimientoInventario
        fields = ("insumo", "tipo", "cantidad", "motivo")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tipo"].choices = [
            (MovimientoInventario.Tipo.ENTRADA, "Entrada"),
            (MovimientoInventario.Tipo.AJUSTE, "Ajuste"),
        ]

    def clean(self):
        limpio = super().clean()
        insumo = limpio.get("insumo")
        tipo = limpio.get("tipo")
        cantidad = limpio.get("cantidad")
        if tipo == MovimientoInventario.Tipo.CONSUMO:
            raise ValidationError("El consumo solo se registra al iniciar la preparación.")
        if insumo is not None and not insumo.activo:
            raise ValidationError(MENSAJE_INACTIVO)
        if insumo is not None and cantidad is not None and tipo == MovimientoInventario.Tipo.AJUSTE:
            if insumo.existencia + cantidad < 0:
                raise ValidationError(MENSAJE_EXISTENCIA)
        if tipo == MovimientoInventario.Tipo.ENTRADA and cantidad is not None and cantidad <= 0:
            self.add_error("cantidad", "La entrada debe ser mayor que cero.")
        return limpio


class MovimientoInventarioAdmin(admin.ModelAdmin):
    form = FormularioMovimiento
    list_display = ("creada", "insumo", "tipo", "cantidad", "existencia_resultante", "usuario")
    readonly_fields = ("existencia_resultante", "creada", "pedido", "usuario")

    def get_changeform_initial_data(self, request):
        return {"clave_solicitud": secrets.token_hex(16)}

    def save_model(self, request, obj, form, change):
        if change:
            raise ValidationError("Un movimiento registrado no se modifica.")
        movimiento, _creado = registrar_movimiento(
            insumo=form.cleaned_data["insumo"],
            tipo=form.cleaned_data["tipo"],
            cantidad=form.cleaned_data["cantidad"],
            motivo=form.cleaned_data["motivo"],
            usuario=request.user,
            clave=form.cleaned_data["clave_solicitud"],
        )
        obj.pk = movimiento.pk

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class IngredienteInline(admin.TabularInline):
    model = RecetaIngrediente
    extra = 1


class RecetaAdmin(admin.ModelAdmin):
    list_display = ("producto", "variante", "rendimiento")
    inlines = [IngredienteInline]
    exclude = ("alcance",)


class ConsumoPedidoAdmin(admin.ModelAdmin):
    list_display = ("pedido", "usuario", "creada")
    readonly_fields = ("pedido", "usuario", "creada")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(Insumo, InsumoAdmin)
admin.site.register(MovimientoInventario, MovimientoInventarioAdmin)
admin.site.register(Receta, RecetaAdmin)
admin.site.register(ConsumoPedido, ConsumoPedidoAdmin)
