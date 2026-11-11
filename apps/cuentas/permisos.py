from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import PermissionDenied

from .models import Usuario


class RequiereRolMixin(UserPassesTestMixin):
    roles = ()

    def test_func(self):
        usuario = self.request.user
        if not usuario.is_authenticated or not usuario.is_active:
            return False
        if usuario.is_superuser and Usuario.Rol.ADMINISTRADORA in self.roles:
            return True
        return usuario.rol in self.roles

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied("No tienes permiso para entrar aquí.")
        return super().handle_no_permission()
