"""Registro de clientes y destinos según el rol.

El alta pública no acepta rol ni banderas de permiso: esos valores se
fijan aquí. El nombre de usuario interno no se muestra en el formulario.
"""

import re

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.urls import reverse

from .models import Usuario

MENSAJE_CORREO_REPETIDO = "Ya existe una cuenta con ese correo."
MENSAJE_CORREO_NO_DISPONIBLE = "No pudimos crear la cuenta con ese correo. Usa otro."
MENSAJE_TELEFONO = "Ingresa un teléfono válido. Puedes usar un número chileno o internacional."
_SEPARADORES = re.compile(r"[\s().-]+")


def normalizar_correo(valor):
    return (valor or "").strip().lower()


def normalizar_telefono(valor):
    limpio = _SEPARADORES.sub("", (valor or "").strip())
    if limpio.startswith("00"):
        limpio = "+" + limpio[2:]
    if not re.fullmatch(r"\+?\d{8,15}", limpio or ""):
        raise ValidationError(MENSAJE_TELEFONO)
    if limpio.startswith("+"):
        return limpio
    if re.fullmatch(r"9\d{8}", limpio) or re.fullmatch(r"\d{9}", limpio):
        return "+56" + limpio
    if re.fullmatch(r"56\d{9}", limpio):
        return "+" + limpio
    raise ValidationError(MENSAJE_TELEFONO)


def _base_username(correo):
    if len(correo) <= 150:
        return correo
    local, separador, dominio = correo.partition("@")
    resumen = f"{local[:40]}@{dominio}" if separador else local
    return resumen[:150]


def generar_username(correo):
    base = _base_username(correo)
    if not Usuario.objects.filter(username__iexact=base).exists():
        return base
    for indice in range(1, 1000):
        sufijo = f"-{indice}"
        candidato = f"{base[:150 - len(sufijo)]}{sufijo}"
        if not Usuario.objects.filter(username__iexact=candidato).exists():
            return candidato
    raise ValidationError("No pudimos crear la cuenta. Intenta nuevamente.")


def destino_por_rol(usuario):
    if usuario.is_superuser or usuario.rol == Usuario.Rol.ADMINISTRADORA:
        return reverse("gestion")
    if usuario.rol == Usuario.Rol.AYUDANTE:
        return reverse("trabajo")
    return reverse("mi_cuenta")


def etiqueta_por_rol(usuario):
    if usuario.is_superuser or usuario.rol == Usuario.Rol.ADMINISTRADORA:
        return "Gestión"
    if usuario.rol == Usuario.Rol.AYUDANTE:
        return "Trabajo"
    return "Mi cuenta"


def etiqueta_opcional(texto):
    from django.utils.html import format_html

    return format_html('{} <span class="etiqueta-opcional">(opcional)</span>', texto)


def _apellido_completo(paterno, materno=""):
    partes = [(paterno or "").strip(), (materno or "").strip()]
    return " ".join(parte for parte in partes if parte)


@transaction.atomic
def registrar_ayudante(*, nombre, apellido_paterno, apellido_materno, correo, telefono, password):
    """Crea una ayudante. El rol y los privilegios no se aceptan desde fuera."""
    correo = normalizar_correo(correo)
    telefono = normalizar_telefono(telefono)
    validate_password(password)
    if Usuario.objects.filter(email__iexact=correo).exclude(email="").exists():
        raise ValidationError(MENSAJE_CORREO_REPETIDO)
    if Usuario.objects.filter(username__iexact=correo).exists():
        raise ValidationError(MENSAJE_CORREO_NO_DISPONIBLE)
    usuario = Usuario(
        username=generar_username(correo),
        email=correo,
        first_name=(nombre or "").strip(),
        last_name=_apellido_completo(apellido_paterno, apellido_materno),
        telefono=telefono,
        rol=Usuario.Rol.AYUDANTE,
        is_staff=False,
        is_superuser=False,
        is_active=True,
    )
    usuario.set_password(password)
    try:
        usuario.save()
    except IntegrityError as exc:
        raise ValidationError(MENSAJE_CORREO_REPETIDO) from exc
    return usuario


@transaction.atomic
def registrar_cliente(*, nombre, apellido, correo, telefono, password, apellido_materno=""):
    correo = normalizar_correo(correo)
    telefono = normalizar_telefono(telefono)
    validate_password(password)
    if Usuario.objects.filter(email__iexact=correo).exclude(email="").exists():
        raise ValidationError(MENSAJE_CORREO_REPETIDO)
    if Usuario.objects.filter(username__iexact=correo).exists():
        raise ValidationError(MENSAJE_CORREO_NO_DISPONIBLE)
    usuario = Usuario(
        username=generar_username(correo),
        email=correo,
        first_name=(nombre or "").strip(),
        last_name=_apellido_completo(apellido, apellido_materno),
        telefono=telefono,
        rol=Usuario.Rol.CLIENTE,
        is_staff=False,
        is_superuser=False,
        is_active=True,
    )
    usuario.set_password(password)
    try:
        usuario.save()
    except IntegrityError as exc:
        raise ValidationError(MENSAJE_CORREO_REPETIDO) from exc
    return usuario


@transaction.atomic
def actualizar_datos_personales(*, usuario, nombre, apellido_paterno, apellido_materno, correo, telefono):
    """Actualiza la ficha propia. No toca el rol ni los permisos."""
    correo = normalizar_correo(correo)
    if correo and Usuario.objects.filter(email__iexact=correo).exclude(pk=usuario.pk).exists():
        raise ValidationError(MENSAJE_CORREO_REPETIDO)
    if correo and Usuario.objects.filter(username__iexact=correo).exclude(pk=usuario.pk).exists():
        raise ValidationError(MENSAJE_CORREO_NO_DISPONIBLE)
    telefono = normalizar_telefono(telefono) if (telefono or "").strip() else ""
    usuario.first_name = (nombre or "").strip()
    usuario.last_name = _apellido_completo(apellido_paterno, apellido_materno)
    usuario.email = correo
    usuario.telefono = telefono
    usuario.save(update_fields=["first_name", "last_name", "email", "telefono"])
    return usuario
