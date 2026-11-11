from django.http import Http404
from django.views.generic import TemplateView

from .consultas import catalogo_publico, detalle_publico


class CatalogoPublicoView(TemplateView):
    template_name = "catalogo/indice.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(catalogo_publico())
        return contexto


class ProductoDetalleView(TemplateView):
    template_name = "catalogo/detalle.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        detalle = detalle_publico(self.kwargs["slug"])
        if detalle is None:
            raise Http404("Ese producto no está publicado.")
        contexto.update(detalle)
        return contexto
