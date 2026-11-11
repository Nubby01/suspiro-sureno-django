from django import forms

from apps.catalogo.formularios import precio_entero, texto_precio
from apps.cuentas.servicios import normalizar_correo, normalizar_telefono


class SolicitudForm(forms.Form):
    nombre = forms.CharField(
        label="Nombre",
        max_length=120,
        error_messages={"required": "Completa el nombre."},
    )
    correo = forms.EmailField(
        label="Correo electrónico",
        error_messages={"required": "Completa el correo electrónico."},
    )
    telefono = forms.CharField(
        label="Teléfono",
        max_length=20,
        error_messages={"required": "Completa el teléfono."},
    )
    observaciones = forms.CharField(
        label="Observaciones",
        required=False,
        max_length=1000,
        widget=forms.Textarea(attrs={"rows": 4}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            campo.widget.attrs["class"] = "entrada"
        self.fields["nombre"].widget.attrs["placeholder"] = "Ej.: Ana Soto"
        self.fields["correo"].widget.attrs["placeholder"] = "Ej.: ana@correo.cl"
        self.fields["telefono"].widget.attrs["placeholder"] = "Ej.: +56 9 1234 5678"
        self.fields["observaciones"].widget.attrs["placeholder"] = "Indica detalles especiales de tu pedido"

    def clean_nombre(self):
        return (self.cleaned_data.get("nombre") or "").strip()

    def clean_correo(self):
        return normalizar_correo(self.cleaned_data.get("correo"))

    def clean_telefono(self):
        return normalizar_telefono(self.cleaned_data.get("telefono"))

    def clean_observaciones(self):
        return (self.cleaned_data.get("observaciones") or "").strip()


class PreciosForm(forms.Form):
    def __init__(self, lineas, *args, **kwargs):
        self.lineas = list(lineas)
        super().__init__(*args, **kwargs)
        for linea in self.lineas:
            campo = forms.CharField(
                label=linea.nombre_producto,
                required=False,
                help_text="Vacío significa precio pendiente. Cero es un precio acordado.",
            )
            campo.widget.attrs["class"] = "entrada"
            campo.initial = texto_precio(linea.precio_acordado)
            self.fields[f"precio_{linea.pk}"] = campo

    def clean(self):
        limpio = super().clean()
        self.precios = {}
        for linea in self.lineas:
            self.precios[linea.pk] = precio_entero(limpio.get(f"precio_{linea.pk}"))
        return limpio


class MotivoForm(forms.Form):
    motivo = forms.CharField(
        label="Motivo",
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 3, "class": "entrada"}),
        error_messages={"required": "Indica el motivo."},
    )
