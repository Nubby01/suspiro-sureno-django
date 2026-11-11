"""Formularios del catálogo. Los campos sensibles no se aceptan desde el POST."""

import re
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

from .edicion import actualizar_producto, crear_producto_simple
from .imagenes import etiqueta_fotografia, fotografias_disponibles, referencia_es_segura, validar_referencia
from .models import Categoria, Producto
from .servicios import MENSAJE_PRECIO_INVALIDO


def precio_entero(valor):
    texto = str(valor).strip() if valor is not None else ""
    if not texto:
        return None
    if not re.fullmatch(r"\d{1,10}", texto):
        raise ValidationError(MENSAJE_PRECIO_INVALIDO)
    return Decimal(texto)


def texto_precio(precio):
    if precio is None:
        return ""
    return format(precio, "f")


def opciones_fotografia(actual=""):
    opciones = [("", "Sin fotografía")]
    vistas = set()
    for ruta in fotografias_disponibles():
        if ruta not in vistas:
            opciones.append((ruta, etiqueta_fotografia(ruta)))
            vistas.add(ruta)
    actual = (actual or "").strip()
    if actual and actual not in vistas and referencia_es_segura(actual):
        opciones.append((actual, etiqueta_fotografia(actual)))
    return opciones


def _estilo(formulario):
    for campo in formulario.fields.values():
        if isinstance(campo.widget, forms.CheckboxInput):
            campo.widget.attrs["class"] = "casilla"
        else:
            campo.widget.attrs.setdefault("class", "entrada")


class ProductoNuevoForm(forms.Form):
    nombre = forms.CharField(
        label="Nombre",
        max_length=120,
        error_messages={"required": "Completa el nombre."},
    )
    descripcion = forms.CharField(
        label="Descripción",
        required=False,
        max_length=4000,
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    categoria = forms.ModelChoiceField(
        label="Categoría",
        queryset=Categoria.objects.order_by("orden", "nombre"),
        error_messages={"required": "Elige una categoría."},
    )
    referencia_imagen = forms.ChoiceField(
        label="Fotografía",
        required=False,
        choices=[("", "Sin fotografía")],
        error_messages={"invalid_choice": "Elige una fotografía del catálogo o deja el campo vacío."},
    )
    precio = forms.CharField(
        label="Precio minorista",
        required=False,
        help_text="Precio público. Vacío significa «Consultar precio». Cero es un precio real. Escríbelo sin puntos ni comas.",
    )
    precio_mayorista = forms.CharField(
        label="Precio mayorista",
        required=False,
        help_text="Uso interno. No se publica y no se aplica según la cantidad. Vacío significa que no hay precio mayorista.",
    )
    activo = forms.BooleanField(
        label="Producto activo",
        required=False,
        initial=True,
        help_text="Si lo desactivas, deja de verse en el catálogo público y el registro se conserva.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["referencia_imagen"].choices = opciones_fotografia()
        _estilo(self)

    def clean_nombre(self):
        return (self.cleaned_data.get("nombre") or "").strip()

    def clean_descripcion(self):
        return (self.cleaned_data.get("descripcion") or "").strip()

    def clean_referencia_imagen(self):
        return validar_referencia(self.cleaned_data.get("referencia_imagen"))

    def clean_precio(self):
        return precio_entero(self.cleaned_data.get("precio"))

    def clean_precio_mayorista(self):
        return precio_entero(self.cleaned_data.get("precio_mayorista"))

    def crear(self):
        datos = self.cleaned_data
        return crear_producto_simple(
            categoria=datos["categoria"],
            nombre=datos["nombre"],
            descripcion=datos["descripcion"],
            activo=datos["activo"],
            referencia_imagen=datos["referencia_imagen"],
            precio=datos["precio"],
            precio_mayorista=datos["precio_mayorista"],
        )


class ProductoEditarForm(forms.Form):
    nombre = forms.CharField(
        label="Nombre",
        max_length=120,
        error_messages={"required": "Completa el nombre."},
    )
    descripcion = forms.CharField(
        label="Descripción",
        required=False,
        max_length=4000,
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    categoria = forms.ModelChoiceField(
        label="Categoría",
        queryset=Categoria.objects.order_by("orden", "nombre"),
        error_messages={"required": "Elige una categoría."},
    )
    referencia_imagen = forms.ChoiceField(
        label="Fotografía",
        required=False,
        choices=[("", "Sin fotografía")],
        error_messages={"invalid_choice": "Elige una fotografía del catálogo o deja el campo vacío."},
    )
    activo = forms.BooleanField(
        label="Producto activo",
        required=False,
        help_text="Si lo desactivas, deja de verse en el catálogo público y el registro se conserva.",
    )

    def __init__(self, producto, *args, **kwargs):
        self.producto = producto
        super().__init__(*args, **kwargs)
        self.fields["referencia_imagen"].choices = opciones_fotografia(producto.referencia_imagen)
        self.fields["nombre"].initial = producto.nombre
        self.fields["descripcion"].initial = producto.descripcion
        self.fields["categoria"].initial = producto.categoria_id
        self.fields["referencia_imagen"].initial = producto.referencia_imagen
        self.fields["activo"].initial = producto.activo
        _estilo(self)

    def clean_nombre(self):
        return (self.cleaned_data.get("nombre") or "").strip()

    def clean_descripcion(self):
        return (self.cleaned_data.get("descripcion") or "").strip()

    def clean_referencia_imagen(self):
        return validar_referencia(self.cleaned_data.get("referencia_imagen"))

    def guardar(self):
        datos = self.cleaned_data
        return actualizar_producto(
            producto=self.producto,
            nombre=datos["nombre"],
            descripcion=datos["descripcion"],
            categoria=datos["categoria"],
            activo=datos["activo"],
            referencia_imagen=datos["referencia_imagen"],
        )


class VarianteEdicionForm(forms.Form):
    id = forms.IntegerField(widget=forms.HiddenInput)
    nombre = forms.CharField(label="Nombre", max_length=80, required=False)
    precio = forms.CharField(
        label="Precio minorista",
        required=False,
        help_text="Precio público. Vacío significa «Consultar precio».",
    )
    precio_mayorista = forms.CharField(
        label="Precio mayorista",
        required=False,
        help_text="Uso interno. No se publica y no se aplica según la cantidad.",
    )
    orden = forms.IntegerField(
        label="Orden",
        min_value=0,
        error_messages={
            "invalid": "El orden debe ser un número entero.",
            "min_value": "El orden no puede ser negativo.",
            "required": "Completa el orden.",
        },
    )
    activa = forms.BooleanField(label="Activa", required=False)
    es_predeterminada = forms.BooleanField(label="Predeterminada", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _estilo(self)

    def clean_nombre(self):
        return (self.cleaned_data.get("nombre") or "").strip()

    def clean_precio(self):
        return precio_entero(self.cleaned_data.get("precio"))

    def clean_precio_mayorista(self):
        return precio_entero(self.cleaned_data.get("precio_mayorista"))


VarianteFormSet = forms.formset_factory(VarianteEdicionForm, extra=0, max_num=20)


class VarianteNuevaForm(forms.Form):
    nombre = forms.CharField(label="Nombre", max_length=80, required=False)
    precio = forms.CharField(
        label="Precio minorista",
        required=False,
        help_text="Precio público. Vacío significa «Consultar precio». Si el producto queda con varias variantes, cada una necesita nombre.",
    )
    precio_mayorista = forms.CharField(
        label="Precio mayorista",
        required=False,
        help_text="Uso interno. No se publica y no se aplica según la cantidad.",
    )
    orden = forms.IntegerField(label="Orden", min_value=0, initial=0, required=False)
    activa = forms.BooleanField(label="Activa", required=False, initial=True)
    es_predeterminada = forms.BooleanField(label="Predeterminada", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _estilo(self)

    def clean_nombre(self):
        return (self.cleaned_data.get("nombre") or "").strip()

    def clean_precio(self):
        return precio_entero(self.cleaned_data.get("precio"))

    def clean_precio_mayorista(self):
        return precio_entero(self.cleaned_data.get("precio_mayorista"))

    def clean_orden(self):
        orden = self.cleaned_data.get("orden")
        return 0 if orden is None else orden


class GaleriaAgregarForm(forms.Form):
    producto_origen = forms.ModelChoiceField(
        label="Producto de origen",
        queryset=Producto.objects.none(),
        required=False,
        error_messages={
            "invalid_choice": "Elige un producto de origen distinto o deja el campo vacío.",
        },
        help_text="Si eliges un producto, se reutilizan su nombre y su fotografía. No se crea otra variante ni se copia el archivo.",
    )
    nombre = forms.CharField(
        label="Nombre del sabor",
        max_length=120,
        required=False,
        help_text="Úsalo solo cuando el sabor no es un producto del catálogo.",
    )
    referencia_imagen = forms.ChoiceField(
        label="Fotografía",
        required=False,
        choices=[("", "Sin fotografía")],
        error_messages={"invalid_choice": "Elige una fotografía del catálogo o deja el campo vacío."},
    )
    orden = forms.IntegerField(label="Orden", min_value=0, required=False)

    def __init__(self, producto, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["producto_origen"].queryset = Producto.objects.exclude(pk=producto.pk).order_by("nombre")
        self.fields["referencia_imagen"].choices = opciones_fotografia()
        _estilo(self)

    def clean_nombre(self):
        return (self.cleaned_data.get("nombre") or "").strip()

    def clean_referencia_imagen(self):
        return validar_referencia(self.cleaned_data.get("referencia_imagen"))

    def clean_orden(self):
        return self.cleaned_data.get("orden")
