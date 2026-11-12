"""Crear y editar el catálogo. Solo la administradora, y sin borrar productos."""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import FormView

from apps.catalogo.consultas import formato_clp
from apps.catalogo.edicion import (
    agregar_a_galeria,
    agregar_variante_panel,
    guardar_orden_galeria,
    guardar_variantes,
    quitar_de_galeria,
)
from apps.catalogo.formularios import (
    GaleriaAgregarForm,
    ProductoEditarForm,
    ProductoNuevoForm,
    VarianteFormSet,
    VarianteNuevaForm,
    texto_precio,
)
from apps.catalogo.imagenes import fotografia_publica
from apps.catalogo.models import Producto
from apps.cuentas.models import Usuario
from apps.cuentas.permisos import RequiereRolMixin
from apps.inventario.consultas_recetas import recetas_del_producto

from .navegacion import contexto_panel


def _panel(titulo, introduccion):
    panel = dict(contexto_panel("gestion"))
    panel["titulo"] = titulo
    panel["introduccion"] = introduccion
    return panel


def _precio_visible(producto):
    variante = producto.variantes.filter(es_predeterminada=True).first()
    if variante is None:
        return "Sin variante predeterminada"
    if variante.precio is None:
        return "Consultar precio"
    return formato_clp(variante.precio)


def _iniciales_variantes(producto):
    return [
        {
            "id": variante.pk,
            "nombre": variante.nombre,
            "precio": texto_precio(variante.precio),
            "precio_mayorista": texto_precio(variante.precio_mayorista),
            "orden": variante.orden,
            "activa": variante.activa,
            "es_predeterminada": variante.es_predeterminada,
        }
        for variante in producto.variantes.order_by("orden", "id")
    ]


def _sabores(producto):
    filas = []
    for elemento in producto.galeria.select_related("producto_origen").order_by("orden", "id"):
        nombre = elemento.nombre
        referencia = elemento.referencia_imagen
        if elemento.producto_origen_id:
            nombre = nombre or elemento.producto_origen.nombre
            referencia = referencia or elemento.producto_origen.referencia_imagen
        foto = fotografia_publica(referencia, nombre or "sabor")
        filas.append(
            {
                "id": elemento.pk,
                "nombre": nombre,
                "orden": elemento.orden,
                "imagen": foto["imagen"],
                "imagen_alt": foto["imagen_alt"],
                "imagen_ancho": foto["imagen_ancho"],
                "imagen_alto": foto["imagen_alto"],
            }
        )
    return filas


class ProductoNuevoView(RequiereRolMixin, FormView):
    template_name = "panel/catalogo_formulario.html"
    form_class = ProductoNuevoForm
    roles = (Usuario.Rol.ADMINISTRADORA,)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["panel"] = _panel(
            "Nuevo producto",
            "El producto queda con una variante predeterminada. El precio vacío se muestra como «Consultar precio».",
        )
        contexto["cuenta"] = self.request.user
        contexto["enviar"] = "Crear producto"
        contexto["producto"] = None
        return contexto

    def form_valid(self, form):
        try:
            producto = form.crear()
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        messages.success(self.request, "El producto quedó creado.")
        return redirect("catalogo_editar", producto_id=producto.pk)


class ProductoEditarView(RequiereRolMixin, FormView):
    template_name = "panel/catalogo_formulario.html"
    form_class = ProductoEditarForm
    roles = (Usuario.Rol.ADMINISTRADORA,)

    def get_producto(self):
        if not hasattr(self, "producto"):
            self.producto = get_object_or_404(Producto, pk=self.kwargs["producto_id"])
        return self.producto

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["producto"] = self.get_producto()
        return kwargs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        producto = self.get_producto()
        contexto["panel"] = _panel(
            producto.nombre,
            "Puedes cambiar el nombre, la descripción, la categoría, la fotografía y el estado. El registro no se elimina.",
        )
        contexto["cuenta"] = self.request.user
        contexto["enviar"] = "Guardar producto"
        contexto["producto"] = producto
        contexto["precio_texto"] = _precio_visible(producto)
        contexto["foto"] = fotografia_publica(producto.referencia_imagen, producto.nombre)
        contexto.update(recetas_del_producto(producto))
        return contexto

    def form_valid(self, form):
        try:
            producto = form.guardar()
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        messages.success(self.request, "El producto quedó guardado.")
        return redirect("catalogo_editar", producto_id=producto.pk)


class VariantesGestionView(RequiereRolMixin, View):
    roles = (Usuario.Rol.ADMINISTRADORA,)

    def get_producto(self):
        return get_object_or_404(Producto, pk=self.kwargs["producto_id"])

    def get(self, request, producto_id):
        producto = self.get_producto()
        return self._render(
            request,
            producto,
            VarianteFormSet(initial=_iniciales_variantes(producto), prefix="variantes"),
            VarianteNuevaForm(prefix="nueva"),
        )

    def post(self, request, producto_id):
        producto = self.get_producto()
        if request.POST.get("accion") == "agregar":
            nueva = VarianteNuevaForm(request.POST, prefix="nueva")
            formset = VarianteFormSet(initial=_iniciales_variantes(producto), prefix="variantes")
            if not nueva.is_valid():
                return self._render(request, producto, formset, nueva)
            try:
                agregar_variante_panel(
                    producto=producto,
                    nombre=nueva.cleaned_data["nombre"],
                    precio=nueva.cleaned_data["precio"],
                    precio_mayorista=nueva.cleaned_data["precio_mayorista"],
                    orden=nueva.cleaned_data["orden"],
                    activa=nueva.cleaned_data["activa"],
                    es_predeterminada=nueva.cleaned_data["es_predeterminada"],
                )
            except ValidationError as exc:
                nueva.add_error(None, exc)
                return self._render(request, producto, formset, nueva)
            messages.success(request, "La variante quedó agregada.")
            return redirect("catalogo_variantes", producto_id=producto.pk)

        formset = VarianteFormSet(request.POST, prefix="variantes")
        nueva = VarianteNuevaForm(prefix="nueva")
        if not formset.is_valid():
            return self._render(request, producto, formset, nueva)
        try:
            guardar_variantes(
                producto,
                [
                    {
                        "id": fila["id"],
                        "nombre": fila["nombre"],
                        "precio": fila["precio"],
                        "precio_mayorista": fila["precio_mayorista"],
                        "orden": fila["orden"],
                        "activa": fila["activa"],
                        "es_predeterminada": fila["es_predeterminada"],
                    }
                    for fila in formset.cleaned_data
                    if fila
                ],
            )
        except ValidationError as exc:
            formset._non_form_errors = formset.error_class(exc.messages)
            return self._render(request, producto, formset, nueva)
        messages.success(request, "Las variantes quedaron guardadas.")
        return redirect("catalogo_variantes", producto_id=producto.pk)

    def _render(self, request, producto, formset, nueva):
        return render(
            request,
            "panel/catalogo_variantes.html",
            {
                "panel": _panel(
                    f"Variantes de {producto.nombre}",
                    "El precio minorista es el público. El mayorista queda solo en este panel y no cambia según la cantidad.",
                ),
                "cuenta": request.user,
                "producto": producto,
                "formset": formset,
                "nueva": nueva,
            },
        )


class GaleriaGestionView(RequiereRolMixin, View):
    roles = (Usuario.Rol.ADMINISTRADORA,)

    def get_producto(self):
        return get_object_or_404(Producto, pk=self.kwargs["producto_id"])

    def get(self, request, producto_id):
        producto = self.get_producto()
        return self._render(request, producto, GaleriaAgregarForm(producto, prefix="sabor"))

    def post(self, request, producto_id):
        producto = self.get_producto()
        accion = request.POST.get("accion")
        formulario = GaleriaAgregarForm(producto, prefix="sabor")
        try:
            if accion == "agregar":
                formulario = GaleriaAgregarForm(producto, request.POST, prefix="sabor")
                if not formulario.is_valid():
                    return self._render(request, producto, formulario)
                agregar_a_galeria(
                    producto=producto,
                    producto_origen=formulario.cleaned_data["producto_origen"],
                    nombre=formulario.cleaned_data["nombre"],
                    referencia_imagen=formulario.cleaned_data["referencia_imagen"],
                    orden=formulario.cleaned_data["orden"],
                )
                messages.success(request, "El sabor quedó en la galería.")
            elif accion == "quitar":
                quitar_de_galeria(producto=producto, elemento_id=request.POST.get("elemento"))
                messages.success(request, "El sabor salió de la galería. El producto de origen se conservó.")
            elif accion == "ordenar":
                guardar_orden_galeria(producto=producto, ordenes=_ordenes_publicados(request, producto))
                messages.success(request, "El orden de la galería quedó guardado.")
            else:
                formulario.add_error(None, "No se reconoció la acción.")
                return self._render(request, producto, formulario)
        except ValidationError as exc:
            if accion == "agregar":
                formulario.add_error(None, exc)
                return self._render(request, producto, formulario)
            messages.error(request, " ".join(exc.messages))
        return redirect("catalogo_galeria", producto_id=producto.pk)

    def _render(self, request, producto, formulario):
        return render(
            request,
            "panel/catalogo_galeria.html",
            {
                "panel": _panel(
                    f"Galería de {producto.nombre}",
                    "Cada sabor muestra su fotografía y su nombre. La galería no publica un precio por sabor.",
                ),
                "cuenta": request.user,
                "producto": producto,
                "sabores": _sabores(producto),
                "formulario": formulario,
            },
        )


def _ordenes_publicados(request, producto):
    ordenes = {}
    for elemento in producto.galeria.all():
        crudo = (request.POST.get(f"orden-{elemento.pk}") or "").strip()
        if not crudo.isdigit() or int(crudo) > 100000:
            raise ValidationError("El orden debe ser un número entero.")
        ordenes[elemento.pk] = int(crudo)
    return ordenes
