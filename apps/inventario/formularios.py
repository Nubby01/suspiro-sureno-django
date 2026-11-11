from django import forms
from django.utils import timezone

from apps.catalogo.models import Producto, VarianteProducto

from .models import Insumo
from .servicios import cantidad_exacta


class _Base(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            campo.widget.attrs.setdefault("class", "entrada")


class InsumoForm(_Base):
    nombre = forms.CharField(label="Nombre", max_length=120)
    unidad = forms.ChoiceField(label="Unidad", choices=Insumo.Unidad.choices)
    stock_minimo = forms.CharField(
        label="Stock mínimo",
        help_text="Se avisa cuando la existencia es igual o menor que este valor.",
    )
    stock_critico = forms.CharField(label="Stock crítico", required=False, help_text="Umbral absoluto en la unidad del insumo. Vacío: sin nivel crítico. No puede superar el mínimo. Cero se distingue como agotado.")
    activo = forms.BooleanField(label="Activo", required=False, initial=True)

    def clean_stock_critico(self):
        valor = self.cleaned_data.get("stock_critico")
        return None if not valor else cantidad_exacta(valor, minimo=0, permitir_cero=True)

    def clean(self):
        datos = super().clean()
        minimo, critico = datos.get("stock_minimo"), datos.get("stock_critico")
        if minimo is not None and critico is not None and critico > minimo:
            self.add_error("stock_critico", "No puede superar el stock mínimo.")
        return datos

    def clean_nombre(self):
        return (self.cleaned_data.get("nombre") or "").strip()

    def clean_stock_minimo(self):
        return cantidad_exacta(
            self.cleaned_data.get("stock_minimo"),
            minimo=0,
            permitir_cero=True,
        )


class MovimientoForm(_Base):
    insumo = forms.ModelChoiceField(
        label="Insumo",
        queryset=Insumo.objects.filter(activo=True).order_by("nombre"),
    )
    cantidad = forms.CharField(label="Cantidad", help_text="Cantidad en la unidad del insumo elegido. Ej.: 5 kg si el insumo usa kilogramos. Hasta 3 decimales.")
    motivo = forms.CharField(label="Motivo", max_length=500, widget=forms.Textarea(attrs={"rows": 3}))
    clave = forms.CharField(widget=forms.HiddenInput)

    def clean_motivo(self):
        return (self.cleaned_data.get("motivo") or "").strip()


class EntradaForm(MovimientoForm):
    es_compra = forms.BooleanField(label="Es una compra", required=False, help_text="Una entrada no implica una compra. Marca solo si corresponde.")
    fecha_compra = forms.DateField(label="Fecha de compra", required=False, widget=forms.DateInput(attrs={"type":"date"}, format="%Y-%m-%d"), input_formats=["%Y-%m-%d"])
    precio_compra = forms.DecimalField(label="Importe total de compra (CLP)", min_value=0, max_digits=12, decimal_places=2, required=False)
    proveedor = forms.CharField(label="Proveedor u origen", max_length=160, required=False)
    caducidad = forms.DateField(label="Fecha de caducidad", required=False, widget=forms.DateInput(attrs={"type":"date"}, format="%Y-%m-%d"), input_formats=["%Y-%m-%d"])
    lote = forms.CharField(label="Referencia de lote", max_length=100, required=False)
    observaciones = forms.CharField(label="Observaciones del abastecimiento", max_length=1000, required=False, widget=forms.Textarea(attrs={"rows":3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fecha_compra"].widget.attrs["max"] = timezone.localdate().isoformat()
        self.fields["fecha_compra"].help_text = "Opcional. No puede ser posterior a hoy."
        self.fields["caducidad"].help_text = "Opcional. No puede ser anterior a la compra; admite registros históricos."
        for nombre in ("fecha_compra", "caducidad"):
            self.fields[nombre].error_messages["invalid"] = "Introduce una fecha válida."

    def clean(self):
        datos = super().clean()
        compra, caducidad = datos.get("fecha_compra"), datos.get("caducidad")
        if compra and compra > timezone.localdate():
            self.add_error("fecha_compra", "La fecha de compra no puede ser posterior a hoy.")
        if compra and caducidad and caducidad < compra:
            self.add_error("caducidad", "La caducidad no puede ser anterior a la fecha de compra.")
        if not datos.get("es_compra") and (datos.get("fecha_compra") or datos.get("precio_compra") is not None):
            self.add_error("es_compra", "Marca compra o deja fecha e importe de compra vacíos.")
        return datos

    def clean_cantidad(self):
        return cantidad_exacta(self.cleaned_data.get("cantidad"), minimo=0)


class AjusteForm(MovimientoForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cantidad"].help_text = (
            "Número positivo para aumentar y negativo para disminuir. "
            "No deja la existencia bajo cero."
        )

    def clean_cantidad(self):
        return cantidad_exacta(self.cleaned_data.get("cantidad"))


class RecetaForm(_Base):
    producto = forms.ModelChoiceField(
        label="Producto",
        queryset=Producto.objects.order_by("nombre"),
    )
    variante = forms.ModelChoiceField(
        label="Variante",
        queryset=VarianteProducto.objects.select_related("producto").order_by("producto__nombre", "orden", "id"),
        required=False,
        help_text="Vacío aplica la receta a todo el producto. Si eliges una variante, solo vale para esa variante.",
    )
    rendimiento = forms.CharField(
        label="Rendimiento",
        help_text="Unidades del producto que produce la receta. Por ejemplo, 1.",
    )
    insumo = forms.ModelChoiceField(label="Insumo", queryset=Insumo.objects.order_by("nombre"))
    unidad = forms.ChoiceField(label="Unidad", choices=Insumo.Unidad.choices)
    cantidad = forms.CharField(
        label="Cantidad requerida",
        help_text="Cantidad del insumo, en su unidad, para el rendimiento indicado.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["variante"].label_from_instance = (
            lambda variante: variante.producto.nombre
            + (f" — {variante.nombre}" if variante.nombre else " — presentación inicial")
        )

    def clean_rendimiento(self):
        return cantidad_exacta(self.cleaned_data.get("rendimiento"), minimo=0)

    def clean_cantidad(self):
        return cantidad_exacta(self.cleaned_data.get("cantidad"), minimo=0)

    def clean(self):
        limpio = super().clean()
        producto = limpio.get("producto")
        variante = limpio.get("variante")
        insumo = limpio.get("insumo")
        if variante is not None and producto is not None and variante.producto_id != producto.pk:
            self.add_error("variante", "La variante no pertenece a ese producto.")
        if insumo is not None and limpio.get("unidad") and limpio.get("unidad") != insumo.unidad:
            self.add_error("unidad", "La unidad debe ser la misma del insumo.")
        return limpio
