"""Cuentas locales para revisar permisos.

No guarda contraseñas en el código. El comando las pide por consola y
no modifica cuentas que no lleven el prefijo de demostración.
"""

import getpass

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.cuentas.models import Usuario

CUENTAS = (
    {
        "username": "demo-administradora",
        "email": "demo-administradora@example.com",
        "rol": Usuario.Rol.ADMINISTRADORA,
        "etiqueta": "administradora de demostración",
    },
    {
        "username": "demo-ayudante",
        "email": "demo-ayudante@example.com",
        "rol": Usuario.Rol.AYUDANTE,
        "etiqueta": "ayudante de demostración",
    },
    {
        "username": "demo-clienta",
        "email": "demo-clienta@example.com",
        "rol": Usuario.Rol.CLIENTE,
        "etiqueta": "clienta de demostración",
    },
)


def entorno_local_permitido():
    base = settings.DATABASES["default"]
    if base.get("ENGINE") != "django.db.backends.sqlite3":
        return False
    if getattr(settings, "PERMITIR_CUENTAS_DEMOSTRACION", False):
        return True
    nombre = str(base.get("NAME", ""))
    return bool(settings.DEBUG) and nombre.endswith("db.sqlite3")


def asegurar_cuenta(definicion, clave):
    """Crea una cuenta de demostración. No borra ni toca otras cuentas."""
    existente = Usuario.objects.filter(username=definicion["username"]).first()
    if existente is not None:
        if (
            existente.rol != definicion["rol"]
            or existente.is_staff
            or existente.is_superuser
            or not existente.is_active
        ):
            raise ValidationError(
                f"La cuenta {definicion['username']} ya existe y no se modificó."
            )
        return existente, False
    validate_password(clave)
    usuario = Usuario(
        username=definicion["username"],
        email=definicion["email"],
        rol=definicion["rol"],
        is_staff=False,
        is_superuser=False,
        is_active=True,
    )
    usuario.set_password(clave)
    usuario.save()
    return usuario, True


class Command(BaseCommand):
    help = (
        "Crea, solo en la base SQLite local, las cuentas de demostración "
        "que todavía no existen. Pide cada contraseña por consola."
    )

    def handle(self, *args, **options):
        if not entorno_local_permitido():
            raise CommandError(
                "Este comando solo puede usarse en el desarrollo local, "
                "con DEBUG activo y la base SQLite del proyecto."
            )
        for definicion in CUENTAS:
            if Usuario.objects.filter(username=definicion["username"]).exists():
                try:
                    asegurar_cuenta(definicion, "")
                except ValidationError as exc:
                    raise CommandError(str(exc)) from exc
                self.stdout.write(f"{definicion['username']} ya existe y se dejó igual.")
                continue
            clave = getpass.getpass(f"Contraseña para {definicion['etiqueta']}: ")
            confirmacion = getpass.getpass("Confírmala: ")
            if clave != confirmacion:
                raise CommandError(
                    f"Las contraseñas de {definicion['username']} no coinciden. "
                    "No se creó esa cuenta."
                )
            try:
                asegurar_cuenta(definicion, clave)
            except ValidationError as exc:
                raise CommandError(str(exc)) from exc
            self.stdout.write(f"{definicion['username']} quedó creada.")
