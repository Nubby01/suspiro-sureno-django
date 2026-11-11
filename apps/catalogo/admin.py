from django.contrib import admin
from django.db import transaction
from django.forms import ModelForm, Select
from django.forms.models import BaseInlineFormSet

from .consultas import formato_clp
from .imagenes import (
    AYUDA_REFERENCIA,
    etiqueta_fotografia,
    fotografias_disponibles,
    validar_referencia,
)
from .models import Categoria, ElementoGaleria, Producto, VarianteProducto
from .servicios import (
    cambiar_variante_predeterminada,
    validar_producto_para_venta,
    validar_variantes,
)


class _VarianteVista:
    def __init__(self, nombre, precio, es_predeterminada, activa):
        self.nombre = nombre
        self.precio = precio
        self.es_predeterminada = es_predeterminada
        self.activa = activa


def _vistas_desde_instancias(instancias):
    return [
        _VarianteVista(
            nombre=instancia.nombre,
            precio=instancia.precio,
            es_predeterminada=instancia.es_predeterminada,
            activa=instancia.activa,
        )
        for instancia in instancias
    ]


class VarianteInlineFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        propuestas = []
        for form in self.forms:
            if not getattr(form, "cleaned_data", None):
                continue
            if form.cleaned_data.get("DELETE"):
                continue
            if not form.instance.pk and not form.has_changed():
                continue
            propuestas.append(form.instance)
        validar_variantes(_vistas_desde_instancias(propuestas), bool(self.instance.activo))

    def save(self, commit=True):
        if not commit:
            return super().save(commit=False)
        with transaction.atomic():
            self.changed_objects = []
            self.deleted_objects = []
            self.new_objects = []
            for form in self.deleted_forms:
                obj = form.instance
                if obj.pk is not None:
                    self.deleted_objects.append(obj)
                    obj.delete()
            pendientes = []
            for form in list(self.initial_forms) + list(self.extra_forms):
                if form in self.deleted_forms or self._should_delete_form(form):
                    continue
                if form in self.extra_forms and not form.has_changed():
                    continue
                if form in self.initial_forms and not form.has_changed():
                    continue
                pendientes.append((form, form.save(commit=False)))
            pendientes.sort(key=lambda par: bool(par[1].es_predeterminada))
            guardadas = []
            for form, obj in pendientes:
                obj.save()
                form.save_m2m()
                guardadas.append(obj)
                if form in self.extra_forms:
                    self.new_objects.append(obj)
                else:
                    self.changed_objects.append((obj, form.changed_data))
            if self.instance.pk:
                validar_producto_para_venta(self.instance)
            return guardadas


def precio_visible(variante):
    if variante.precio is None:
        return "Consultar precio"
    return formato_clp(variante.precio)


class VarianteProductoInline(admin.TabularInline):
    model = VarianteProducto
    formset = VarianteInlineFormSet
    extra = 1
    fields = ("nombre", "precio", "precio_mayorista", "es_predeterminada", "orden", "activa")


class VarianteProductoForm(ModelForm):
    class Meta:
        model = VarianteProducto
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        if self.errors:
            return cleaned
        producto = cleaned.get("producto")
        if producto is None or not producto.pk:
            return cleaned
        propuesta = _VarianteVista(
            nombre=(cleaned.get("nombre") or "").strip(),
            precio=cleaned.get("precio"),
            es_predeterminada=bool(cleaned.get("es_predeterminada")),
            activa=bool(cleaned.get("activa")),
        )
        hermanas = []
        for actual in producto.variantes.all():
            if self.instance.pk and actual.pk == self.instance.pk:
                continue
            es_predeterminada = actual.es_predeterminada
            if propuesta.es_predeterminada:
                es_predeterminada = False
            hermanas.append(
                _VarianteVista(
                    nombre=actual.nombre,
                    precio=actual.precio,
                    es_predeterminada=es_predeterminada,
                    activa=actual.activa,
                )
            )
        hermanas.append(propuesta)
        validar_variantes(hermanas, producto.activo)
        return cleaned

    def save(self, commit=True):
        quiere_predeterminada = bool(self.cleaned_data.get("es_predeterminada"))
        if not commit:
            if quiere_predeterminada:
                self.instance.es_predeterminada = False
            return super().save(commit=False)
        with transaction.atomic():
            if quiere_predeterminada:
                self.instance.es_predeterminada = False
            obj = super().save(commit=True)
            if quiere_predeterminada:
                return cambiar_variante_predeterminada(obj)
            validar_producto_para_venta(obj.producto)
            return obj


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "slug", "orden", "activa")
    search_fields = ("nombre", "slug")
    list_filter = ("activa",)
    ordering = ("orden", "nombre")


class ProductoForm(ModelForm):
    class Meta:
        model = Producto
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        campo = self.fields["referencia_imagen"]
        opciones = [("", "Sin fotografía")]
        opciones.extend((ruta, etiqueta_fotografia(ruta)) for ruta in fotografias_disponibles())
        actual = (getattr(self.instance, "referencia_imagen", "") or "").strip()
        if actual and actual not in {valor for valor, _etiqueta in opciones}:
            opciones.append((actual, "Ruta guardada no disponible"))
        campo.widget = Select(choices=opciones)
        campo.required = False
        campo.help_text = AYUDA_REFERENCIA

    def clean_referencia_imagen(self):
        return validar_referencia(self.cleaned_data.get("referencia_imagen"))


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    form = ProductoForm
    list_display = ("nombre", "categoria", "activo")
    search_fields = ("nombre",)
    list_filter = ("categoria", "activo")
    ordering = ("nombre",)
    inlines = (VarianteProductoInline,)
    prepopulated_fields = {"slug": ("nombre",)}

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(VarianteProducto)
class VarianteProductoAdmin(admin.ModelAdmin):
    form = VarianteProductoForm
    list_display = ("producto", "nombre", "precio_en_lista", "mayorista_en_lista", "activa", "es_predeterminada")

    @admin.display(description="precio minorista", ordering="precio")
    def precio_en_lista(self, obj):
        return precio_visible(obj)

    @admin.display(description="precio mayorista", ordering="precio_mayorista")
    def mayorista_en_lista(self, obj):
        if obj.precio_mayorista is None:
            return "Sin precio mayorista"
        return formato_clp(obj.precio_mayorista)

    search_fields = ("nombre", "producto__nombre")
    list_filter = ("activa", "es_predeterminada")
    ordering = ("producto__nombre", "orden")


class ElementoGaleriaForm(ModelForm):
    class Meta:
        model = ElementoGaleria
        fields = "__all__"

    def clean_referencia_imagen(self):
        return validar_referencia(self.cleaned_data.get("referencia_imagen"))


@admin.register(ElementoGaleria)
class ElementoGaleriaAdmin(admin.ModelAdmin):
    form = ElementoGaleriaForm
    list_display = ("producto", "producto_origen", "nombre", "orden")
    list_filter = ("producto",)
    ordering = ("producto__nombre", "orden", "id")
