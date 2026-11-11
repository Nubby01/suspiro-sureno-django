from django.views.generic import TemplateView

from .presentacion import (
    CATEGORIAS,
    FAVORITOS_MUESTRA,
    FOTO_ESENCIA,
    FOTO_HERO,
    boton_si_existe,
)


class InicioView(TemplateView):
    template_name = "core/inicio.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        from apps.catalogo.consultas import catalogo_publico
        grupos = catalogo_publico()["grupos"]
        contexto["categorias"] = [
            {"clave": grupo["slug"], "titulo": grupo["nombre"], "descripcion": grupo["descripcion"],
             "destino": grupo["id"], "imagen": next((producto["imagen"] for producto in grupo["productos"] if producto.get("imagen")), "")}
            for grupo in grupos
        ]
        contexto["favoritos_muestra"] = FAVORITOS_MUESTRA
        contexto["foto_hero"] = FOTO_HERO
        contexto["foto_esencia"] = FOTO_ESENCIA
        contexto["boton_catalogo"] = boton_si_existe("catalogo", "Explorar catálogo")
        contexto["boton_cotizar"] = boton_si_existe("cotizaciones", "Cotizar mi pedido")
        return contexto
