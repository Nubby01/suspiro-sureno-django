"""Ruta única de la fotografía de un producto.

El campo `Producto.referencia_imagen` guarda una ruta relativa a los
archivos estáticos, o queda vacío. El formato es:

    imagenes/catalogo-web/rollopizzacatalogo.jpg

Django la resuelve con `{% static %}`. No se guardan rutas de Windows,
direcciones externas ni archivos de `MEDIA`.

Las copias de `static/imagenes/catalogo-web/` son JPEG. La portada
confirmada de Rollitos de sabores es el PNG real
`static/imagenes/rollossabores.png`: se referencia, no se convierte.
"""

import re
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError

PREFIJO = "imagenes/catalogo-web/"
PORTADA_ROLLOS = "imagenes/rollossabores.png"
PATRON_REFERENCIA = re.compile(r"^imagenes/catalogo-web/[a-z0-9]+\.jpg$")
MENSAJE_RUTA = (
    "Indique una ruta relativa del catálogo, como "
    "imagenes/catalogo-web/rollopizzacatalogo.jpg, o deje el campo vacío."
)
MENSAJE_AUSENTE = "Esa fotografía no está entre las copias optimizadas del catálogo."
AYUDA_REFERENCIA = (
    "Elija una copia de static/imagenes/catalogo-web/ o deje «Sin fotografía». "
    "Se guarda solo la ruta relativa, por ejemplo "
    "imagenes/catalogo-web/rollopizzacatalogo.jpg."
)


def referencia_es_segura(valor):
    if valor == PORTADA_ROLLOS:
        return True
    return bool(PATRON_REFERENCIA.fullmatch(valor or ""))


def etiqueta_fotografia(ruta):
    if ruta == PORTADA_ROLLOS:
        return "rollossabores.png"
    return ruta.removeprefix(PREFIJO)


def _raiz_estatica(base):
    return Path(base).resolve()


def ruta_fisica(ruta):
    """Devuelve el archivo estático si la ruta es segura y permanece dentro de static."""
    if not referencia_es_segura(ruta):
        return None
    for base in settings.STATICFILES_DIRS:
        raiz = _raiz_estatica(base)
        candidato = (raiz / ruta).resolve()
        if candidato.is_file() and raiz in candidato.parents:
            return candidato
    return None


def fotografias_disponibles():
    encontradas = []
    vistas = set()
    for base in settings.STATICFILES_DIRS:
        carpeta = Path(base) / "imagenes" / "catalogo-web"
        if not carpeta.is_dir():
            continue
        raiz = _raiz_estatica(base)
        for archivo in sorted(carpeta.glob("*.jpg"), key=lambda item: item.name):
            candidato = archivo.resolve()
            if not candidato.is_file() or raiz not in candidato.parents:
                continue
            ruta = f"{PREFIJO}{archivo.name}"
            if referencia_es_segura(ruta) and ruta not in vistas:
                vistas.add(ruta)
                encontradas.append(ruta)
    if ruta_fisica(PORTADA_ROLLOS) and PORTADA_ROLLOS not in vistas:
        encontradas.append(PORTADA_ROLLOS)
    return encontradas


def validar_referencia(valor):
    """Normaliza el valor del admin. Vacío es válido."""
    texto = (valor or "").strip()
    if not texto:
        return ""
    if not referencia_es_segura(texto):
        raise ValidationError(MENSAJE_RUTA)
    if ruta_fisica(texto) is None:
        raise ValidationError(MENSAJE_AUSENTE)
    return texto


def _dimensiones(archivo):
    cabecera = archivo.read_bytes()[:32]
    if cabecera[:8] == b"\x89PNG\r\n\x1a\n" and len(cabecera) >= 24:
        ancho = int.from_bytes(cabecera[16:20], "big")
        alto = int.from_bytes(cabecera[20:24], "big")
        if ancho > 0 and alto > 0:
            return (ancho, alto)
    return _dimensiones_jpeg(archivo)


def _dimensiones_jpeg(archivo):
    datos = archivo.read_bytes()[:65536]
    if len(datos) < 11 or datos[:2] != b"\xff\xd8":
        return (3, 2)
    indice = 2
    while indice + 9 < len(datos):
        if datos[indice] != 0xFF:
            break
        marcador = datos[indice + 1]
        if marcador in (0x01, 0xD8) or 0xD0 <= marcador <= 0xD9:
            if marcador == 0xD9:
                break
            indice += 2
            continue
        largo = int.from_bytes(datos[indice + 2 : indice + 4], "big")
        if largo < 2 or indice + 2 + largo > len(datos):
            break
        if marcador in (0xC0, 0xC1, 0xC2):
            alto = int.from_bytes(datos[indice + 5 : indice + 7], "big")
            ancho = int.from_bytes(datos[indice + 7 : indice + 9], "big")
            if ancho > 0 and alto > 0:
                return (ancho, alto)
        indice += 2 + largo
    return (3, 2)


def fotografia_publica(referencia, nombre_producto):
    """Datos de la ficha. Una ruta vacía, ajena o inexistente no produce imagen."""
    archivo = ruta_fisica((referencia or "").strip())
    if archivo is None:
        return {
            "imagen": "",
            "imagen_alt": "",
            "imagen_ancho": 3,
            "imagen_alto": 2,
            "imagen_diferida": True,
        }
    ancho, alto = _dimensiones(archivo)
    return {
        "imagen": (referencia or "").strip(),
        "imagen_alt": f"Fotografía de {nombre_producto}",
        "imagen_ancho": ancho,
        "imagen_alto": alto,
        "imagen_diferida": True,
    }
