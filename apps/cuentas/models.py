from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.db.models.functions import Lower


class UsuarioManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("rol", Usuario.Rol.ADMINISTRADORA)
        return super().create_superuser(username, email, password, **extra_fields)


class Usuario(AbstractUser):
    """Cuenta del sitio. El visitante no tiene fila: simplemente no inicia sesión."""

    class Rol(models.TextChoices):
        ADMINISTRADORA = "administradora", "Administradora"
        AYUDANTE = "ayudante", "Ayudante"
        CLIENTE = "cliente", "Cliente"

    rol = models.CharField(
        "rol",
        max_length=20,
        choices=Rol.choices,
        default=Rol.CLIENTE,
    )
    telefono = models.CharField("teléfono", max_length=20, blank=True)

    objects = UsuarioManager()

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        constraints = [
            models.UniqueConstraint(
                Lower("email"),
                condition=~models.Q(email=""),
                name="correo_usuario_unico",
                violation_error_message="Ya existe una cuenta con ese correo.",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)
