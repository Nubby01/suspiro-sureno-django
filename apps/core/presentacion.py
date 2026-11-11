"""Piezas visuales de la portada.

Los favoritos de muestra no son productos: no salen de la base de datos
y no se ofrecen a la venta. Las fotografías se reemplazan solo cuando
exista un archivo autorizado.
"""

from django.urls import NoReverseMatch, reverse

# Nombres previstos para cuando esas páginas existan de verdad.
CANDIDATOS_NAV = (
    ("inicio", "Inicio"),
    ("catalogo", "Catálogo"),
    ("cotizaciones", "Cotizaciones"),
)

CATEGORIAS = (
    {
        "clave": "alfajores",
        "titulo": "Alfajores",
        "descripcion": "Pieza individual de masa y relleno.",
        "foto_pendiente": "Alfajores de cerca, con luz cálida y fondo neutro.",
    },
    {
        "clave": "tortas",
        "titulo": "Tortas y cheesecakes",
        "descripcion": "Preparaciones para compartir en la mesa.",
        "foto_pendiente": "Una torta o un cheesecake entero, sin texto ni precio.",
    },
    {
        "clave": "kuchen",
        "titulo": "Kuchen y pies",
        "descripcion": "Masas dulces de horno.",
        "foto_pendiente": "Un kuchen o un pie, visto de lado.",
    },
    {
        "clave": "rollitos",
        "titulo": "Rollitos",
        "descripcion": "Bizcocho enrollado, en porción.",
        "foto_pendiente": "Rollitos en porción, con el corte visible.",
    },
    {
        "clave": "berlines",
        "titulo": "Berlines",
        "descripcion": "Masa frita, rellena al centro.",
        "foto_pendiente": "Berlines agrupados, con el relleno apenas visible.",
    },
)

FAVORITOS_MUESTRA = (
    {
        "clave": "alfajor",
        "titulo": "Alfajor de muestra",
        "descripcion": "Tarjeta de demostración para un alfajor.",
        "foto_pendiente": "Un alfajor, de cerca, con luz cálida.",
        "es_muestra": True,
    },
    {
        "clave": "torta",
        "titulo": "Torta de muestra",
        "descripcion": "Tarjeta de demostración para una torta.",
        "foto_pendiente": "Una torta o cheesecake, sin precio visible.",
        "es_muestra": True,
    },
    {
        "clave": "kuchen",
        "titulo": "Kuchen de muestra",
        "descripcion": "Tarjeta de demostración para un kuchen.",
        "foto_pendiente": "Un kuchen o pie recién cortado.",
        "es_muestra": True,
    },
    {
        "clave": "berlines",
        "titulo": "Berlines de muestra",
        "descripcion": "Tarjeta de demostración para un berlín.",
        "foto_pendiente": "Berlines en grupo, sobre mesa clara.",
        "es_muestra": True,
    },
)

FOTO_HERO = "Fotografía principal de la repostería o del taller, con luz cálida y sin texto incrustado."
FOTO_ESENCIA = "Elaboración artesanal en el taller: manos o mesa de trabajo, en Punta Arenas."


def enlaces_disponibles():
    enlaces = []
    for nombre, etiqueta in CANDIDATOS_NAV:
        try:
            url = reverse(nombre)
        except NoReverseMatch:
            continue
        enlaces.append({"nombre": nombre, "etiqueta": etiqueta, "url": url})
    return enlaces


def boton_si_existe(nombre, etiqueta):
    try:
        url = reverse(nombre)
    except NoReverseMatch:
        return {"etiqueta": etiqueta, "url": "", "activo": False}
    return {"etiqueta": etiqueta, "url": url, "activo": True}
