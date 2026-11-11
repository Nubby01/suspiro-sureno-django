"""Datos públicos confirmados de Suspiro Sureño.

No incluye dirección, horarios, medios de pago ni información tributaria.
"""

import os
from urllib.parse import quote

NOMBRE = "Suspiro Sureño"
DESCRIPCION = "Repostería artesanal hecha con dedicación."
WHATSAPP_VISIBLE = os.environ.get("NEGOCIO_WHATSAPP_VISIBLE", "")
WHATSAPP_NUMERO = os.environ.get("NEGOCIO_WHATSAPP_NUMERO", "")
CORREO = os.environ.get("NEGOCIO_CORREO", "")
INSTAGRAM = os.environ.get("NEGOCIO_INSTAGRAM", "")
FACEBOOK = os.environ.get("NEGOCIO_FACEBOOK", "")


def mensaje_whatsapp(codigo=None, lineas=None):
    """Texto para que la persona lo envíe ella misma desde WhatsApp."""
    if codigo:
        texto = f"Hola, Suspiro Sureño. Quisiera consultar por mi cotización {codigo}."
    else:
        texto = "Hola, Suspiro Sureño. Quisiera consultar por una cotización."
    for linea in list(lineas or [])[:6]:
        if isinstance(linea, dict):
            nombre = linea.get("nombre") or linea.get("nombre_producto") or ""
            cantidad = linea.get("cantidad") or ""
        else:
            nombre = getattr(linea, "nombre_producto", "") or getattr(linea, "nombre", "")
            cantidad = getattr(linea, "cantidad", "")
        nombre = str(nombre).strip()
        if nombre and cantidad:
            texto += f"\n- {nombre} x {cantidad}"
    return texto


def url_whatsapp(codigo=None, lineas=None):
    if not WHATSAPP_NUMERO:
        return ""
    return f"https://wa.me/{WHATSAPP_NUMERO}?text={quote(mensaje_whatsapp(codigo, lineas))}"


def datos_publicos():
    return {
        "nombre": NOMBRE,
        "descripcion": DESCRIPCION,
        "whatsapp_visible": WHATSAPP_VISIBLE,
        "whatsapp": f"https://wa.me/{WHATSAPP_NUMERO}" if WHATSAPP_NUMERO else "",
        "whatsapp_consulta": url_whatsapp(),
        "correo": CORREO,
        "correo_url": f"mailto:{CORREO}" if CORREO else "",
        "instagram": INSTAGRAM,
        "facebook": FACEBOOK,
    }
