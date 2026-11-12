from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import FormView, TemplateView

from apps.cuentas.models import Usuario
from apps.cuentas.permisos import RequiereRolMixin

from .demostracion import filtro_demo
from .forms import AyudanteForm
from .listado import listado_interno
from .navegacion import contexto_panel
from .resumen import resumen_gestion
from .dashboard import dashboard_gestion, dashboard_trabajo


class _PanelView(RequiereRolMixin, TemplateView):
    panel = ""

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["panel"] = contexto_panel(self.panel)
        contexto["cuenta"] = self.request.user
        return contexto


class GestionView(_PanelView):
    template_name = "panel/dashboard_gestion.html"
    panel = "gestion"
    roles = (Usuario.Rol.ADMINISTRADORA,)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["resumen"] = resumen_gestion()
        contexto["comercial"] = dashboard_gestion()
        return contexto


class TrabajoView(_PanelView):
    template_name = "panel/dashboard_trabajo.html"
    panel = "trabajo"
    roles = (Usuario.Rol.AYUDANTE, Usuario.Rol.ADMINISTRADORA)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["jornada"] = dashboard_trabajo(self.request.user)
        return contexto


class CatalogoInternoView(RequiereRolMixin, TemplateView):
    template_name = "panel/catalogo.html"
    roles = (Usuario.Rol.ADMINISTRADORA,)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        panel = dict(contexto_panel("gestion"))
        panel["titulo"] = "Catálogo"
        panel["introduccion"] = (
            "Listado de los productos registrados. "
            "Desde aquí puedes crearlos y editarlos. Desactivar conserva el registro."
        )
        contexto["panel"] = panel
        contexto["cuenta"] = self.request.user
        contexto.update(
            listado_interno(
                request=self.request,
                busqueda=self.request.GET.get("q", ""),
                categoria=self.request.GET.get("categoria", ""),
            )
        )
        return contexto


class PersonalView(RequiereRolMixin, FormView):
    template_name = "panel/personal.html"
    form_class = AyudanteForm
    roles = (Usuario.Rol.ADMINISTRADORA,)
    success_url = reverse_lazy("personal")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        panel = dict(contexto_panel("gestion"))
        panel["titulo"] = "Personal"
        panel["introduccion"] = "Registra una ayudante y consulta el personal autorizado."
        contexto["panel"] = panel
        contexto["cuenta"] = self.request.user
        contexto["personal"] = (
            Usuario.objects.filter(
                Q(rol__in=(Usuario.Rol.ADMINISTRADORA, Usuario.Rol.AYUDANTE)) | Q(is_superuser=True)
            )
            .order_by("first_name", "last_name", "username")
        )
        contexto["personal"] = filtro_demo(contexto["personal"], self.request, "username")
        return contexto

    def form_valid(self, form):
        try:
            usuario = form.save()
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        messages.success(
            self.request,
            f"La cuenta de ayudante de {usuario.get_full_name()} quedó creada.",
        )
        return super().form_valid(form)


class ClientesView(RequiereRolMixin, TemplateView):
    template_name = "panel/clientes.html"
    roles = (Usuario.Rol.ADMINISTRADORA,)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        panel = dict(contexto_panel("gestion"))
        panel["titulo"] = "Clientes"
        panel["introduccion"] = "Consulta las cuentas de clientas registradas."
        texto = (self.request.GET.get("q") or "").strip()
        clientes = filtro_demo(Usuario.objects.filter(rol=Usuario.Rol.CLIENTE, is_superuser=False), self.request, "username")
        if texto:
            clientes = clientes.filter(
                Q(first_name__icontains=texto)
                | Q(last_name__icontains=texto)
                | Q(email__icontains=texto)
            )
        contexto["panel"] = panel
        contexto["cuenta"] = self.request.user
        contexto["clientes"] = clientes.order_by("-date_joined", "id")
        contexto["busqueda"] = texto
        return contexto


class ClienteDetalleView(RequiereRolMixin, TemplateView):
    template_name = "panel/cliente_detalle.html"
    roles = (Usuario.Rol.ADMINISTRADORA,)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        cliente = get_object_or_404(
            Usuario,
            pk=self.kwargs["usuario_id"],
            rol=Usuario.Rol.CLIENTE,
            is_superuser=False,
        )
        panel = dict(contexto_panel("gestion"))
        panel["titulo"] = cliente.get_full_name() or cliente.username
        panel["introduccion"] = "Cotizaciones y pedidos de esta clienta."
        contexto["panel"] = panel
        contexto["cuenta"] = self.request.user
        contexto["cliente"] = cliente
        contexto["cotizaciones"] = cliente.cotizaciones.order_by("-creada")
        contexto["pedidos"] = cliente.pedidos.order_by("-creada")
        return contexto


class AlertasInventarioView(RequiereRolMixin, TemplateView):
    roles = (Usuario.Rol.ADMINISTRADORA,)

    def get(self, request, *args, **kwargs):
        from django.http import JsonResponse
        from django.template.loader import render_to_string
        from .alertas import insumos_con_alerta
        alertas = insumos_con_alerta()
        response = JsonResponse({
            "cantidad": len(alertas),
            "html": render_to_string("panel/_alertas_stock.html", {"alertas_inventario": alertas}),
        })
        response["Cache-Control"] = "no-store, private"
        return response
