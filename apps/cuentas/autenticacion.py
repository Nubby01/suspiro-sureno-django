"""Ingreso por correo o por nombre de usuario.

El admin de Django sigue usando este mismo backend: el superusuario
entra con su nombre de usuario y una clienta con su correo. Si el mismo
texto identifica a dos cuentas distintas, no se inicia sesión.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class CorreoOUsuarioBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        valor = (username or "").strip()
        if not valor or password is None:
            return None
        modelo = get_user_model()
        candidatos = self._candidatos(modelo, valor)
        if len(candidatos) == 1:
            usuario = candidatos[0]
            if usuario.check_password(password) and self.user_can_authenticate(usuario):
                return usuario
            return None
        modelo().set_password(password)
        return None

    def _candidatos(self, modelo, valor):
        vistos = {}
        consultas = [modelo.objects.filter(username__iexact=valor)]
        if "@" in valor:
            consultas.insert(0, modelo.objects.filter(email__iexact=valor).exclude(email=""))
        for consulta in consultas:
            for usuario in consulta:
                vistos[usuario.pk] = usuario
        return list(vistos.values())
