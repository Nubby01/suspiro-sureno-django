"""Lectura explícita del entorno; los mensajes nunca incluyen valores secretos."""
import os
from urllib.parse import urlsplit
from django.core.exceptions import ImproperlyConfigured


def booleano(nombre, defecto=False):
    valor = os.environ.get(nombre)
    if valor is None:
        return defecto
    if valor.strip().lower() in {"1", "true", "yes", "on"}:
        return True
    if valor.strip().lower() in {"0", "false", "no", "off"}:
        return False
    raise ImproperlyConfigured(f"{nombre} debe ser 1 o 0 (también true/false).")


def lista(nombre, defecto=""):
    return [x.strip() for x in os.environ.get(nombre, defecto).split(",") if x.strip()]


def validar_hosts(hosts, produccion=False):
    if produccion and not hosts:
        raise ImproperlyConfigured("Define DJANGO_ALLOWED_HOSTS en producción.")
    if any("*" in x or x.startswith(".") or "://" in x or "/" in x for x in hosts):
        raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS requiere hosts explícitos sin protocolo ni rutas.")


def validar_origenes(origenes, produccion=False):
    if produccion and not origenes:
        raise ImproperlyConfigured("Define DJANGO_CSRF_TRUSTED_ORIGINS en producción.")
    for valor in origenes:
        try:
            url = urlsplit(valor)
            valido = url.scheme in ({"https"} if produccion else {"http", "https"}) and url.hostname and not url.username and not url.password and not url.path and not url.query and not url.fragment and "*" not in valor
            url.port
        except ValueError:
            valido = False
        if not valido:
            raise ImproperlyConfigured("Los orígenes CSRF deben ser direcciones explícitas HTTPS sin rutas en producción.")
