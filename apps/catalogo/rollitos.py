"""Carga de Rollitos de sabores y su galería.

No vuelve a importar los 26 productos iniciales y no escribe precios.
La portada definitiva es el archivo real `static/imagenes/rollossabores.png`.
Si ese archivo no está, se reutiliza una fotografía real ya publicada.
Para reemplazarla:

1. Guardar la imagen en esa ruta, con ese nombre y esa extensión.
2. Ejecutar `python manage.py cargar_rollitos_sabores`.

El comando solo cambia la portada del producto nuevo cuando la actual
sigue siendo la provisional. No toca los rollos individuales.
"""

from django.db import transaction

from .imagenes import PORTADA_ROLLOS, ruta_fisica
from .models import Categoria, ElementoGaleria, Producto
from .servicios import crear_producto_con_variante_inicial

SLUG = "rollitos-de-sabores"
NOMBRE = "Rollitos de sabores"
CATEGORIA_SLUG = "rollos-dulces"
PORTADA_DEFINITIVA = PORTADA_ROLLOS
PORTADA_PROVISIONAL = "imagenes/catalogo-web/rollodecanelacatalogo.jpg"
SABORES = (
    "rollo-de-canela",
    "rollo-de-frambuesa",
    "rollo-oreo",
    "rollo-de-manjar",
    "rollo-de-limon",
    "rollo-tiramisu",
    "rollo-de-canela-y-manzana",
)


class ErrorRollitos(Exception):
    def __init__(self, mensajes):
        if isinstance(mensajes, str):
            mensajes = [mensajes]
        self.mensajes = list(mensajes)
        super().__init__("\n".join(self.mensajes))


def portada_disponible():
    if ruta_fisica(PORTADA_DEFINITIVA):
        return PORTADA_DEFINITIVA, False
    if ruta_fisica(PORTADA_PROVISIONAL):
        return PORTADA_PROVISIONAL, True
    raise ErrorRollitos(
        "No está la portada definitiva ni una fotografía provisional disponible."
    )


@transaction.atomic
def cargar_rollitos():
    categoria = Categoria.objects.filter(slug=CATEGORIA_SLUG).first()
    if categoria is None:
        raise ErrorRollitos("No existe la categoría Rollos dulces.")
    origenes = []
    for slug in SABORES:
        origen = Producto.objects.filter(slug=slug).first()
        if origen is None:
            raise ErrorRollitos(f"Falta el producto individual {slug}.")
        if not ruta_fisica(origen.referencia_imagen):
            raise ErrorRollitos(f"No está la fotografía de {slug}.")
        origenes.append(origen)
    portada, provisional = portada_disponible()
    producto = Producto.objects.filter(slug=SLUG).first()
    creado = producto is None
    if creado:
        producto = crear_producto_con_variante_inicial(
            categoria=categoria,
            nombre=NOMBRE,
            slug=SLUG,
            precio=None,
            descripcion="",
            referencia_imagen=portada,
            activo=True,
            nombre_variante="",
        )
    else:
        if producto.categoria_id != categoria.id:
            raise ErrorRollitos("Rollitos de sabores ya existe en otra categoría.")
        if producto.referencia_imagen == PORTADA_PROVISIONAL and not provisional:
            producto.referencia_imagen = PORTADA_DEFINITIVA
            producto.save(update_fields=["referencia_imagen"])
        elif not (producto.referencia_imagen or "").strip():
            producto.referencia_imagen = portada
            producto.save(update_fields=["referencia_imagen"])
    for orden, origen in enumerate(origenes, start=1):
        elemento, _nuevo = ElementoGaleria.objects.get_or_create(
            producto=producto,
            producto_origen=origen,
            defaults={"orden": orden, "nombre": "", "referencia_imagen": ""},
        )
        if elemento.orden != orden:
            elemento.orden = orden
            elemento.save(update_fields=["orden"])
    return {
        "creado": creado,
        "slug": producto.slug,
        "portada": producto.referencia_imagen,
        "provisional": producto.referencia_imagen != PORTADA_DEFINITIVA,
        "galeria": producto.galeria.count(),
    }
