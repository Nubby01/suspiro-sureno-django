from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import Usuario
from .servicios import (
    MENSAJE_CORREO_NO_DISPONIBLE,
    MENSAJE_CORREO_REPETIDO,
    actualizar_datos_personales,
    etiqueta_opcional,
    normalizar_correo,
    normalizar_telefono,
    registrar_cliente,
)

MENSAJE_INGRESO = "Correo, usuario o contraseña incorrectos."


class RegistroForm(forms.Form):
    first_name = forms.CharField(label="Nombre", max_length=150)
    last_name = forms.CharField(label="Apellido paterno", max_length=150)
    apellido_materno = forms.CharField(
        label=etiqueta_opcional("Apellido materno"),
        max_length=150,
        required=False,
    )
    email = forms.EmailField(label="Correo electrónico")
    telefono = forms.CharField(
        label="Teléfono",
        max_length=20,
        help_text="Puedes usar un número chileno o internacional.",
    )
    password1 = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="Usa al menos 8 caracteres y evita claves muy comunes.",
    )
    password2 = forms.CharField(
        label="Confirmar contraseña",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        autocompletado = {
            "first_name": "given-name",
            "last_name": "family-name",
            "apellido_materno": "additional-name",
            "email": "email",
            "telefono": "tel",
        }
        ejemplos = {
            "first_name": "Ana",
            "last_name": "Soto",
            "apellido_materno": "Pérez",
            "email": "ana@correo.cl",
            "telefono": "+56 9 1234 5678",
        }
        for nombre, campo in self.fields.items():
            campo.widget.attrs.setdefault("class", "entrada")
            if nombre in autocompletado:
                campo.widget.attrs["autocomplete"] = autocompletado[nombre]
            if nombre in ejemplos:
                campo.widget.attrs["placeholder"] = ejemplos[nombre]
        self.fields["telefono"].widget.attrs["inputmode"] = "tel"
        self.fields["email"].widget.attrs["inputmode"] = "email"

    def clean_email(self):
        correo = normalizar_correo(self.cleaned_data["email"])
        if Usuario.objects.filter(email__iexact=correo).exclude(email="").exists():
            raise ValidationError(MENSAJE_CORREO_REPETIDO)
        if Usuario.objects.filter(username__iexact=correo).exists():
            raise ValidationError(MENSAJE_CORREO_NO_DISPONIBLE)
        return correo

    def clean_telefono(self):
        return normalizar_telefono(self.cleaned_data["telefono"])

    def clean(self):
        cleaned = super().clean()
        clave = cleaned.get("password1")
        confirmacion = cleaned.get("password2")
        if clave and confirmacion and clave != confirmacion:
            self.add_error("password2", "Las contraseñas no coinciden.")
        if clave:
            try:
                validate_password(clave)
            except ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned

    def save(self):
        return registrar_cliente(
            nombre=self.cleaned_data["first_name"],
            apellido=self.cleaned_data["last_name"],
            apellido_materno=self.cleaned_data.get("apellido_materno") or "",
            correo=self.cleaned_data["email"],
            telefono=self.cleaned_data["telefono"],
            password=self.cleaned_data["password1"],
        )


class CambiarClaveForm(PasswordChangeForm):
    error_messages = {
        "password_incorrect": "La contraseña actual no es correcta.",
        "password_mismatch": "Las contraseñas nuevas no coinciden.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["old_password"].label = "Contraseña actual"
        self.fields["new_password1"].label = "Nueva contraseña"
        self.fields["new_password2"].label = "Confirmar nueva contraseña"
        self.fields["new_password1"].help_text = "Usa al menos 8 caracteres y evita claves muy comunes."
        self.fields["old_password"].error_messages["required"] = "Ingresa tu contraseña actual."
        self.fields["new_password1"].error_messages["required"] = "Ingresa la nueva contraseña."
        self.fields["new_password2"].error_messages["required"] = "Confirma la nueva contraseña."
        for campo in self.fields.values():
            campo.widget.attrs["class"] = "entrada"
        self.fields["old_password"].widget.attrs["autocomplete"] = "current-password"
        self.fields["new_password1"].widget.attrs["autocomplete"] = "new-password"
        self.fields["new_password2"].widget.attrs["autocomplete"] = "new-password"


class IngresoForm(AuthenticationForm):
    error_messages = {
        "invalid_login": MENSAJE_INGRESO,
        "inactive": MENSAJE_INGRESO,
    }

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        self.fields["username"].label = "Correo electrónico o nombre de usuario"
        self.fields["username"].widget.attrs.update(
            {
                "class": "entrada",
                "autocomplete": "username",
                "autocapitalize": "none",
                "placeholder": "ana@correo.cl",
            }
        )
        self.fields["password"].label = "Contraseña"
        self.fields["password"].widget.attrs.update(
            {"class": "entrada", "autocomplete": "current-password"}
        )


class DatosPersonalesForm(forms.Form):
    first_name = forms.CharField(label="Nombre", max_length=150)
    apellido_paterno = forms.CharField(label="Apellido paterno", max_length=150)
    apellido_materno = forms.CharField(
        label=etiqueta_opcional("Apellido materno"),
        max_length=150,
        required=False,
    )
    email = forms.EmailField(label="Correo electrónico", required=False)
    telefono = forms.CharField(label="Teléfono", max_length=20, required=False)

    def __init__(self, usuario, *args, **kwargs):
        self.usuario = usuario
        super().__init__(*args, **kwargs)
        if not args and not kwargs.get("data"):
            self.initial.setdefault("first_name", usuario.first_name)
            self.initial.setdefault("apellido_paterno", usuario.last_name)
            self.initial.setdefault("email", usuario.email)
            self.initial.setdefault("telefono", usuario.telefono)
        for campo in self.fields.values():
            campo.widget.attrs.setdefault("class", "entrada")
        self.fields["first_name"].widget.attrs["autocomplete"] = "given-name"
        self.fields["apellido_paterno"].widget.attrs["autocomplete"] = "family-name"
        self.fields["apellido_materno"].widget.attrs["autocomplete"] = "additional-name"
        self.fields["email"].widget.attrs["autocomplete"] = "email"
        self.fields["telefono"].widget.attrs.update({"autocomplete": "tel", "inputmode": "tel"})

    def clean_first_name(self):
        nombre = (self.cleaned_data.get("first_name") or "").strip()
        if not nombre:
            raise ValidationError("Completa el nombre.")
        return nombre

    def clean_apellido_paterno(self):
        apellido = (self.cleaned_data.get("apellido_paterno") or "").strip()
        if not apellido:
            raise ValidationError("Completa el apellido.")
        return apellido

    def clean_apellido_materno(self):
        return (self.cleaned_data.get("apellido_materno") or "").strip()

    def clean(self):
        cleaned = super().clean()
        paterno = cleaned.get("apellido_paterno") or ""
        materno = cleaned.get("apellido_materno") or ""
        if paterno and len(f"{paterno} {materno}".strip()) > 150:
            self.add_error("apellido_materno", "Los apellidos juntos no pueden superar 150 caracteres.")
        return cleaned

    def save(self):
        return actualizar_datos_personales(
            usuario=self.usuario,
            nombre=self.cleaned_data["first_name"],
            apellido_paterno=self.cleaned_data["apellido_paterno"],
            apellido_materno=self.cleaned_data.get("apellido_materno") or "",
            correo=self.cleaned_data.get("email") or "",
            telefono=self.cleaned_data.get("telefono") or "",
        )
