from django import template
from django.forms import CheckboxInput
from django.utils.html import format_html
register = template.Library()
AYUDAS = {
 "nombre": "Usa el nombre reconocible del insumo o producto. Ej.: Harina de trigo.",
 "descripcion": "Describe el sabor, relleno o características principales. Máximo 4000 caracteres.",
 "telefono": "Ej.: +56 9 1234 5678. Formato chileno o internacional.",
 "unidad": "Gramos, kilogramos, mililitros, litros o unidades; debe coincidir con el insumo.",
 "motivo": "Explica brevemente el movimiento o cambio. Máximo 500 caracteres.",
 "referencia_imagen": "Selecciona una fotografía existente del catálogo.",
 "fecha_compra": "Fecha real de compra, si se conoce. No se completa automáticamente.",
 "caducidad": "Fecha del envase o lote. Vacío si no se conoce o no corresponde.",
 "lote": "Referencia del envase o proveedor. Opcional; máximo 100 caracteres.",
 "precio_compra": "Importe total pagado en CLP por esta compra, no precio por unidad. Opcional.",
 "proveedor": "Nombre del proveedor u origen del abastecimiento. Opcional.",
 "observaciones": "Incluye solo información necesaria para este registro.",
}
@register.filter
def campo_ui(campo):
    if not hasattr(campo, "field") or campo.is_hidden:
        return campo
    ayuda = "" if campo.help_text else AYUDAS.get(campo.name, "")
    attrs = {"aria-describedby": "pista-"+campo.auto_id} if ayuda else {}
    if getattr(campo.field, "max_length", None):
        attrs["data-longitud"] = campo.field.max_length
    if isinstance(campo.field.widget, CheckboxInput):
        attrs["class"] = "casilla"
    opcional = not campo.field.required and not isinstance(campo.field.widget, CheckboxInput) and "opcional" not in str(campo.label).lower() and "opcional" not in (ayuda + str(campo.help_text)).lower()
    return format_html('{}{}{}', campo.as_widget(attrs=attrs),
                       format_html('<small class="ayuda" id="pista-{}">{}</small>',campo.auto_id,ayuda) if ayuda else "",
                       format_html('<small class="campo-opcional">Opcional</small>') if opcional else "")

@register.filter
def monto_compra(valor):
    if valor is None:
        return "No registrado"
    texto = format(valor, ",.2f").replace(",", "_").replace(".", ",").replace("_", ".")
    return "$" + texto + " CLP"
