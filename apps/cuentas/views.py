import posixpath
from urllib.parse import unquote, urlparse

from django.contrib import messages
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeView
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import FormView, TemplateView

from .forms import CambiarClaveForm, DatosPersonalesForm, IngresoForm, RegistroForm
from .servicios import destino_por_rol


class RegistroView(FormView):
    template_name = "cuentas/registro.html"
    form_class = RegistroForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(destino_por_rol(request.user))
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        try:
            usuario = form.save()
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        login(self.request, usuario, backend="apps.cuentas.autenticacion.CorreoOUsuarioBackend")
        messages.success(self.request, "Tu cuenta quedó creada y la sesión está iniciada.")
        return redirect("mi_cuenta")


def destino_interno_permitido(url):
    """Acepta destinos del sitio y rechaza Django Admin."""
    ruta = unquote(urlparse(url).path or "")
    if not ruta.startswith("/"):
        ruta = "/" + ruta
    normalizada = posixpath.normpath(ruta)
    if not normalizada.startswith("/"):
        normalizada = "/" + normalizada
    return normalizada != "/admin" and not normalizada.startswith("/admin/")


class IngresoView(LoginView):
    template_name = "cuentas/ingresar.html"
    authentication_form = IngresoForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        messages.success(self.request, "Iniciaste sesión correctamente.")
        return respuesta

    def form_invalid(self, form):
        messages.error(self.request, "No pudimos iniciar sesión. Revisa tus datos.")
        return super().form_invalid(form)

    def get_default_redirect_url(self):
        return destino_por_rol(self.request.user)

    def get_redirect_url(self):
        destino = super().get_redirect_url()
        if destino and not destino_interno_permitido(destino):
            return ""
        return destino


class SalirView(LogoutView):
    next_page = reverse_lazy("inicio")

    def post(self, request, *args, **kwargs):
        respuesta = super().post(request, *args, **kwargs)
        messages.success(request, "Cerraste sesión correctamente.")
        return respuesta


class CambiarClaveView(LoginRequiredMixin, PasswordChangeView):
    form_class = CambiarClaveForm
    template_name = "cuentas/cambiar_clave.html"
    success_url = reverse_lazy("mi_cuenta")

    def form_valid(self, form):
        messages.success(self.request, "Tu contraseña quedó actualizada.")
        return super().form_valid(form)


class MiCuentaView(LoginRequiredMixin, TemplateView):
    template_name = "cuentas/mi_cuenta.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        usuario = self.request.user
        contexto["cuenta"] = usuario
        contexto["form_datos"] = kwargs.get("form_datos") or DatosPersonalesForm(usuario)
        contexto["form_clave"] = kwargs.get("form_clave") or CambiarClaveForm(usuario)
        return contexto

    def post(self, request):
        usuario = request.user
        if request.POST.get("accion") == "clave":
            form_clave = CambiarClaveForm(usuario, request.POST)
            if form_clave.is_valid():
                form_clave.save()
                update_session_auth_hash(request, form_clave.user)
                messages.success(request, "Tu contraseña quedó actualizada.")
                return redirect("mi_cuenta")
            return self.render_to_response(self.get_context_data(form_clave=form_clave))
        form_datos = DatosPersonalesForm(usuario, request.POST)
        if form_datos.is_valid():
            form_datos.save()
            messages.success(request, "Tus datos quedaron actualizados.")
            return redirect("mi_cuenta")
        return self.render_to_response(self.get_context_data(form_datos=form_datos))


def error_403(request, exception):
    return render(request, "cuentas/403.html", status=403)
