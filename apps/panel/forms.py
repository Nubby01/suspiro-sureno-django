from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from apps.cuentas.models import Usuario
from apps.cuentas.servicios import (
    MENSAJE_CORREO_NO_DISPONIBLE,
    MENSAJE_CORREO_REPETIDO,
    etiqueta_opcional,
    normalizar_correo,
    normalizar_telefono,
    registrar_ayudante,
)

MENSAJE_APELLIDO = "El apellido paterno es obligatorio."
MENSAJE_APELLIDO_LARGO = "Los apellidos juntos no pueden superar 150 caracteres."


class AyudanteForm(forms.Form):
    first_name = forms.CharField(
        label="Nombre",
        max_length=150,
        error_messages={"required": "Completa el nombre."},
    )
    apellido_paterno = forms.CharField(
        label="Apellido paterno",
        max_length=150,
        error_messages={"required": MENSAJE_APELLIDO},
    )
    apellido_materno = forms.CharField(
        label=etiqueta_opcional("Apellido materno"),
        max_length=150,
        required=False,
    )
    email = forms.EmailField(
        label="Correo electrónico",
        error_messages={"required": "Completa el correo electrónico."},
    )
    telefono = forms.CharField(
        label="Teléfono",
        max_length=20,
        error_messages={"required": "Completa el teléfono."},
    )
    password1 = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="Usa al menos 8 caracteres y evita claves muy comunes.",
        error_messages={"required": "Completa la contraseña."},
    )
    password2 = forms.CharField(
        label="Confirmar contraseña",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        error_messages={"required": "Confirma la contraseña."},
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        autocompletado = {
            "first_name": "given-name",
            "apellido_paterno": "family-name",
            "apellido_materno": "additional-name",
            "email": "email",
            "telefono": "tel",
        }
        for nombre, campo in self.fields.items():
            campo.widget.attrs.setdefault("class", "entrada")
            if nombre in autocompletado:
                campo.widget.attrs["autocomplete"] = autocompletado[nombre]
        self.fields["telefono"].widget.attrs["inputmode"] = "tel"
        self.fields["email"].widget.attrs["inputmode"] = "email"

    def clean_first_name(self):
        return (self.cleaned_data.get("first_name") or "").strip()

    def clean_apellido_paterno(self):
        apellido = (self.cleaned_data.get("apellido_paterno") or "").strip()
        if not apellido:
            raise ValidationError(MENSAJE_APELLIDO)
        return apellido

    def clean_apellido_materno(self):
        return (self.cleaned_data.get("apellido_materno") or "").strip()

    def clean_email(self):
        correo = normalizar_correo(self.cleaned_data.get("email"))
        if Usuario.objects.filter(email__iexact=correo).exclude(email="").exists():
            raise ValidationError(MENSAJE_CORREO_REPETIDO)
        if Usuario.objects.filter(username__iexact=correo).exists():
            raise ValidationError(MENSAJE_CORREO_NO_DISPONIBLE)
        return correo

    def clean_telefono(self):
        return normalizar_telefono(self.cleaned_data.get("telefono"))

    def clean(self):
        cleaned = super().clean()
        paterno = cleaned.get("apellido_paterno") or ""
        materno = cleaned.get("apellido_materno") or ""
        if paterno and len(f"{paterno} {materno}".strip()) > 150:
            self.add_error("apellido_materno", MENSAJE_APELLIDO_LARGO)
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
        return registrar_ayudante(
            nombre=self.cleaned_data["first_name"],
            apellido_paterno=self.cleaned_data["apellido_paterno"],
            apellido_materno=self.cleaned_data.get("apellido_materno") or "",
            correo=self.cleaned_data["email"],
            telefono=self.cleaned_data["telefono"],
            password=self.cleaned_data["password1"],
        )
