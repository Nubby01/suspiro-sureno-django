"""Selecciona SQLite local o PostgreSQL sin conectar ni revelar credenciales."""
from urllib.parse import parse_qs, unquote, urlparse
from django.core.exceptions import ImproperlyConfigured


def configurar_base(url, sqlite_path, produccion=False):
    texto = (url or "").strip()
    if not texto:
        if produccion:
            raise ImproperlyConfigured("DATABASE_URL es obligatoria en producción; SQLite solo se permite en desarrollo.")
        return {"ENGINE": "django.db.backends.sqlite3", "NAME": sqlite_path}
    try:
        analizada = urlparse(texto)
        if analizada.scheme.lower() not in {"postgres", "postgresql"}:
            raise ValueError
        nombre = unquote((analizada.path or "").lstrip("/"))
        if not analizada.hostname or not nombre or not analizada.username or analizada.fragment:
            raise ValueError
        puerto = analizada.port or 5432
        if not 1 <= puerto <= 65535:
            raise ValueError
        consulta = parse_qs(analizada.query)
        modo = (consulta.get("sslmode") or ["require"])[0]
        if modo not in {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}:
            raise ValueError
        if produccion and modo not in {"require", "verify-ca", "verify-full"}:
            raise ImproperlyConfigured("PostgreSQL requiere TLS en producción (sslmode=require o verify-full).")
        opciones = {"sslmode": modo, "connect_timeout": 10}
        for clave in ("channel_binding", "sslrootcert"):
            if clave in consulta:
                opciones[clave] = consulta[clave][0]
        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": nombre, "USER": unquote(analizada.username),
            "PASSWORD": unquote(analizada.password or ""),
            "HOST": analizada.hostname, "PORT": str(puerto),
            "CONN_MAX_AGE": 0,
            "DISABLE_SERVER_SIDE_CURSORS": True,
            "OPTIONS": opciones,
        }
    except (ValueError, TypeError):
        raise ImproperlyConfigured("DATABASE_URL debe ser una URL PostgreSQL válida con host, usuario, base y puerto válido.") from None
