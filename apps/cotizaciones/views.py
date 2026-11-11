from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from apps.catalogo.consultas import formato_clp
from apps.catalogo.imagenes import fotografia_publica
from apps.core.negocio import url_whatsapp
from apps.catalogo.models import VarianteProducto
from apps.catalogo.berlines import SLUG as SLUG_BERLINES
from apps.catalogo.brownie import SLUG as SLUG_BROWNIE
from apps.catalogo.rollitos import SLUG as SLUG_ROLLITOS
from apps.cuentas.models import Usuario
from apps.cuentas.permisos import RequiereRolMixin
from apps.panel.navegacion import contexto_panel
from apps.pedidos.servicios import convertir

from .carrito import actualizar, agregar, leer, vaciar
from .formularios import MotivoForm, PreciosForm, SolicitudForm
from .models import Cotizacion
from .pdf import construir_cotizacion
from .servicios import (
    cantidad_valida,
    cerrar,
    confirmar,
    detalle_centro_brownie,
    detalle_sabores,
    fijar_precios,
    detalle_desde_slugs,
    solicitar,
    variante_publica,
)


def _privada(respuesta):
    respuesta["Cache-Control"] = "private, no-store"
    respuesta["Pragma"] = "no-cache"
    return respuesta


def _origen(valor):
    ruta = (valor or "").split("?", 1)[0]
    if ruta.startswith("/catalogo/") and ".." not in ruta and "\\" not in ruta:
        return ruta
    if ruta == "/catalogo/":
        return ruta
    return reverse("catalogo")


def _presentar(lineas):
    identificadores = [linea["variante_id"] for linea in lineas]
    variantes = {
        variante.pk: variante
        for variante in VarianteProducto.objects.select_related("producto").filter(pk__in=identificadores)
    }
    resultado = []
    for indice, linea in enumerate(lineas):
        variante = variantes.get(linea["variante_id"])
        if variante is None:
            continue
        precio = variante.precio
        try:
            detalle = detalle_desde_slugs(variante, linea["sabores"])
        except ValidationError:
            detalle = "Revisa los sabores de esta línea."
        foto = fotografia_publica(variante.producto.referencia_imagen, variante.producto.nombre)
        resultado.append(
            {
                "indice": indice,
                "nombre": variante.producto.nombre,
                "variante": (variante.nombre or "").strip(),
                "detalle": detalle,
                "cantidad": linea["cantidad"],
                "cantidad_etiqueta": "Cantidad de cajas" if variante.producto.slug in (SLUG_ROLLITOS, SLUG_BERLINES) or "caja" in variante.nombre.lower() else "Cantidad de presentaciones",
                "precio": "Consultar precio" if precio is None else formato_clp(precio),
                "precio_valor": None if precio is None else int(precio),
                "importe": "Consultar precio" if precio is None else formato_clp(precio * linea["cantidad"]),
                "imagen": foto["imagen"],
                "imagen_alt": foto["imagen_alt"],
            }
        )
    return resultado


def _resumen(lineas):
    pendientes = sum(1 for linea in lineas if linea["precio_valor"] is None)
    conocidas = [linea for linea in lineas if linea["precio_valor"] is not None]
    subtotal = sum(linea["precio_valor"] * linea["cantidad"] for linea in conocidas)
    return {
        "presentaciones": len(lineas),
        "piezas": sum(linea["cantidad"] for linea in lineas),
        "pendientes": pendientes,
        "subtotal": formato_clp(subtotal) if conocidas else "",
        "total": formato_clp(subtotal) if lineas and pendientes == 0 else "",
    }


class AgregarCotizacionView(View):
    def get(self, request):
        return redirect("cotizaciones")

    def post(self, request):
        try:
            variante = variante_publica(request.POST.get("variante"))
            cantidad = cantidad_valida(request.POST.get("cantidad"))
            detalle_sabores(variante, request.POST.get("sabor_1"), request.POST.get("sabor_2"))
            codigo_centro = (request.POST.get("sabor_brownie") or "").strip()
            detalle_centro_brownie(variante, codigo_centro)
            sabores = []
            if variante.producto.slug in (SLUG_ROLLITOS, SLUG_BERLINES):
                for sabor in (request.POST.get("sabor_1"), request.POST.get("sabor_2")):
                    slug = (sabor or "").strip()
                    if slug and slug not in sabores:
                        sabores.append(slug)
            elif variante.producto.slug == SLUG_BROWNIE:
                sabores = [codigo_centro]
            agregar(request, variante.pk, cantidad, sabores)
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
            return redirect(_origen(request.POST.get("origen")))
        messages.success(request, "El producto quedó en la cotización.")
        return redirect("cotizaciones")


class SolicitudView(View):
    def get(self, request):
        return self._render(request, self._formulario(request))

    def post(self, request):
        if request.POST.get("accion") == "actualizar":
            return self._actualizar(request)
        formulario = SolicitudForm(request.POST)
        if not formulario.is_valid():
            return self._render(request, formulario)
        try:
            cotizacion = solicitar(
                cliente=request.user,
                nombre=formulario.cleaned_data["nombre"],
                correo=formulario.cleaned_data["correo"],
                telefono=formulario.cleaned_data["telefono"],
                observaciones=formulario.cleaned_data["observaciones"],
                lineas=leer(request),
            )
        except ValidationError as exc:
            formulario.add_error(None, exc)
            return self._render(request, formulario)
        vaciar(request)
        messages.success(request, "La cotización quedó solicitada. Guarda este enlace para consultarla.")
        return _privada(redirect("cotizacion_consulta", token=cotizacion.token))

    def _actualizar(self, request):
        try:
            indice = int(request.POST.get("indice"))
        except (TypeError, ValueError):
            messages.error(request, "No se pudo actualizar esa línea.")
            return redirect("cotizaciones")
        try:
            if request.POST.get("quitar"):
                actualizar(request, indice, None)
                messages.success(request, "Producto eliminado de la cotización.")
            else:
                actualizar(request, indice, cantidad_valida(request.POST.get("cantidad")))
                messages.success(request, "Cantidad actualizada.")
        except (IndexError, ValidationError) as exc:
            mensaje = " ".join(exc.messages) if isinstance(exc, ValidationError) else "No se pudo actualizar esa línea."
            messages.error(request, mensaje)
        return redirect("cotizaciones")

    def _formulario(self, request):
        if request.user.is_authenticated:
            return SolicitudForm(
                initial={
                    "nombre": request.user.get_full_name(),
                    "correo": request.user.email,
                    "telefono": request.user.telefono,
                }
            )
        return SolicitudForm()

    def _render(self, request, formulario):
        lineas = _presentar(leer(request))
        return render(
            request,
            "cotizaciones/solicitud.html",
            {
                "formulario": formulario,
                "lineas": lineas,
                "resumen": _resumen(lineas),
                "whatsapp_url": url_whatsapp(lineas=lineas),
            },
        )


class ConsultaCotizacionView(View):
    def get(self, request, token):
        cotizacion = Cotizacion.objects.filter(token=token).prefetch_related("lineas").first()
        if cotizacion is None:
            raise Http404("No encontramos esa cotización.")
        return _privada(
            render(
                request,
                "cotizaciones/consulta.html",
                {
                    "cotizacion": cotizacion,
                    "whatsapp_url": url_whatsapp(cotizacion.codigo, cotizacion.lineas.all()),
                },
            )
        )


class PdfCotizacionView(View):
    def get(self, request, token):
        cotizacion = Cotizacion.objects.filter(token=token).prefetch_related("lineas").first()
        if cotizacion is None:
            raise Http404("No encontramos esa cotización.")
        return _respuesta_pdf(cotizacion)


class MisCotizacionesView(LoginRequiredMixin, View):
    def get(self, request):
        cotizaciones = Cotizacion.objects.filter(cliente=request.user).prefetch_related("lineas")
        return _privada(render(request, "cotizaciones/mias.html", {"cotizaciones": cotizaciones}))


def _panel(titulo, introduccion):
    panel = dict(contexto_panel("gestion"))
    panel["titulo"] = titulo
    panel["introduccion"] = introduccion
    return panel


def _respuesta_pdf(cotizacion):
    respuesta = HttpResponse(construir_cotizacion(cotizacion), content_type="application/pdf")
    respuesta["Content-Disposition"] = f'attachment; filename="cotizacion-{cotizacion.codigo}.pdf"'
    return _privada(respuesta)


class ListaGestionView(RequiereRolMixin, View):
    roles = (Usuario.Rol.ADMINISTRADORA,)

    def get(self, request):
        texto = " ".join((request.GET.get("q") or "").split())[:120]
        estado = (request.GET.get("estado") or "").strip()
        from apps.panel.demostracion import filtro_demo
        consulta = filtro_demo(Cotizacion.objects.prefetch_related("lineas"), request, "observaciones")
        if texto:
            consulta = consulta.filter(nombre__icontains=texto)
        if estado in Cotizacion.Estado.values:
            consulta = consulta.filter(estado=estado)
        return render(
            request,
            "cotizaciones/gestion_lista.html",
            {
                "panel": _panel(
                    "Cotizaciones",
                    "Solicitudes recibidas. El precio del catálogo no cambia al acordar un valor aquí.",
                ),
                "cuenta": request.user,
                "cotizaciones": consulta,
                "busqueda": texto,
                "estado": estado,
                "estados": Cotizacion.Estado.choices,
            },
        )


class DetalleGestionView(RequiereRolMixin, View):
    roles = (Usuario.Rol.ADMINISTRADORA,)

    def get_cotizacion(self, codigo):
        cotizacion = (
            Cotizacion.objects.filter(codigo=codigo).prefetch_related("lineas").first()
        )
        if cotizacion is None:
            raise Http404("No encontramos esa cotización.")
        return cotizacion

    def get(self, request, codigo):
        cotizacion = self.get_cotizacion(codigo)
        return self._render(request, cotizacion, PreciosForm(cotizacion.lineas.all()), MotivoForm())

    def post(self, request, codigo):
        cotizacion = self.get_cotizacion(codigo)
        accion = request.POST.get("accion")
        precios = PreciosForm(cotizacion.lineas.all(), request.POST)
        motivo = MotivoForm(request.POST)
        try:
            if accion == "precios":
                if not precios.is_valid():
                    return self._render(request, cotizacion, precios, MotivoForm())
                fijar_precios(cotizacion=cotizacion, precios=precios.precios)
                messages.success(request, "Los precios de la cotización quedaron guardados.")
            elif accion == "confirmar":
                confirmar(cotizacion=cotizacion)
                messages.success(request, "La cotización quedó confirmada.")
            elif accion == "rechazar":
                if not motivo.is_valid():
                    return self._render(request, cotizacion, PreciosForm(cotizacion.lineas.all()), motivo)
                cerrar(cotizacion=cotizacion, estado=Cotizacion.Estado.RECHAZADA, motivo=motivo.cleaned_data["motivo"])
                messages.success(request, "La cotización quedó rechazada.")
            elif accion == "cancelar":
                if not motivo.is_valid():
                    return self._render(request, cotizacion, PreciosForm(cotizacion.lineas.all()), motivo)
                cerrar(cotizacion=cotizacion, estado=Cotizacion.Estado.CANCELADA, motivo=motivo.cleaned_data["motivo"])
                messages.success(request, "La cotización quedó cancelada.")
            elif accion == "convertir":
                convertir(cotizacion=cotizacion, usuario=request.user)
                messages.success(request, "La cotización quedó convertida en pedido.")
            else:
                messages.error(request, "No se reconoció la acción.")
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        return redirect("cotizacion_gestion", codigo=cotizacion.codigo)

    def _render(self, request, cotizacion, precios, motivo):
        return _privada(render(
            request,
            "cotizaciones/gestion_detalle.html",
            {
                "panel": _panel(cotizacion.codigo, "Revisa los productos y acuerda los precios antes de confirmar."),
                "cuenta": request.user,
                "cotizacion": cotizacion,
                "precios": precios,
                "motivo": motivo,
                "abierta": cotizacion.estado in Cotizacion.ABIERTAS,
                "confirmada": cotizacion.estado == Cotizacion.Estado.CONFIRMADA,
            },
        ))


class PdfGestionView(RequiereRolMixin, View):
    roles = (Usuario.Rol.ADMINISTRADORA,)

    def get(self, request, codigo):
        cotizacion = Cotizacion.objects.filter(codigo=codigo).prefetch_related("lineas").first()
        if cotizacion is None:
            raise Http404("No encontramos esa cotización.")
        return _respuesta_pdf(cotizacion)
