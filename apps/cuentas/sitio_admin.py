"""Django Admin reservado al mantenimiento técnico.

La puerta es el sitio oficial de Django: todas las rutas internas pasan
por ``has_permission``. Solo un superusuario activo entra. El personal y
las clientas siguen usando ``/cuenta/ingresar/``.
"""

from django.contrib.admin import AdminSite
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import PermissionDenied, ValidationError


MENSAJE_ADMIN = "No se pudo iniciar sesión en el mantenimiento."


class FormularioMantenimiento(AdminAuthenticationForm):
    def confirm_login_allowed(self, user):
        AuthenticationForm.confirm_login_allowed(self, user)
        if not (user.is_active and user.is_superuser):
            raise ValidationError(
                MENSAJE_ADMIN,
                code="invalid_login",
            )


class SitioAdmin(AdminSite):
    site_header = "Mantenimiento de Suspiro Sureño"
    site_title = "Mantenimiento"
    index_title = "Mantenimiento técnico"
    login_form = FormularioMantenimiento

    def has_permission(self, request):
        usuario = request.user
        return bool(
            usuario.is_authenticated and usuario.is_active and usuario.is_superuser
        )

    def admin_view(self, view, cacheable=False):
        protegida = super().admin_view(view, cacheable)

        def inner(request, *args, **kwargs):
            if request.user.is_authenticated and not self.has_permission(request):
                raise PermissionDenied("No tienes permiso para entrar aquí.")
            return protegida(request, *args, **kwargs)

        return inner
