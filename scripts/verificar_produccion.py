"""Verifica producción con datos ficticios y prohíbe cualquier conexión de BD.
Ejecutar: python scripts/verificar_produccion.py
No lee .env, no cambia la configuración del proceso padre ni ejecuta migraciones.
"""
import os
import secrets
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
for clave in list(os.environ):
    if clave.startswith(("DJANGO_", "NEGOCIO_", "VERCEL")) or clave == "DATABASE_URL":
        os.environ.pop(clave)
os.environ.update({
    "DJANGO_SETTINGS_MODULE": "config.settings",
    "DJANGO_LOAD_ENV": "0", "DJANGO_DEBUG": "0", "VERCEL": "1",
    "DJANGO_SECRET_KEY": secrets.token_urlsafe(64),
    "DJANGO_ALLOWED_HOSTS": "proyecto-b.invalid",
    "DJANGO_CSRF_TRUSTED_ORIGINS": "https://proyecto-b.invalid",
    "DATABASE_URL": "postgresql://qa:solo-prueba@neon-inexistente.invalid/proyecto_b?sslmode=require&channel_binding=require",
})


def main():
    import django
    from django.db.backends.base.base import BaseDatabaseWrapper
    with patch.object(BaseDatabaseWrapper, "ensure_connection", side_effect=AssertionError("Conexión prohibida en verificación aislada")):
        django.setup()
        from django.conf import settings
        from django.core.management import call_command
        from django.core.wsgi import get_wsgi_application
        from django.test import Client, RequestFactory
        from django.views.defaults import server_error
        assert not settings.DEBUG
        assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"
        assert settings.DATABASES["default"]["OPTIONS"]["channel_binding"] == "require"
        assert settings.SESSION_ENGINE == "django.contrib.sessions.backends.db"
        assert settings.CSRF_COOKIE_SECURE and settings.SESSION_COOKIE_SECURE
        call_command("check", deploy=True, fail_level="WARNING")
        assert callable(get_wsgi_application())
        client = Client(enforce_csrf_checks=True, HTTP_HOST="proyecto-b.invalid")
        assert client.get("/cuenta/ingresar/").status_code == 301
        seguro = {"HTTP_X_FORWARDED_PROTO": "https"}
        login = client.get("/cuenta/ingresar/", **seguro)
        assert login.status_code == 200
        assert login.cookies["csrftoken"]["secure"]
        assert client.post("/cuenta/ingresar/", {}, **seguro).status_code == 403
        assert client.get("/no-existe-b14/", **seguro).status_code == 404
        assert client.get("/cuenta/ingresar/", HTTP_HOST="ajeno.invalid", **seguro).status_code == 400
        error = server_error(RequestFactory().get("/"))
        assert error.status_code == 500 and b"Traceback" not in error.content
        from decimal import Decimal
        from types import SimpleNamespace
        from time import perf_counter
        from django.utils import timezone
        from apps.cotizaciones.pdf import construir_cotizacion
        linea = SimpleNamespace(nombre_producto="Producto de prueba",nombre_variante="Presentación QA",detalle="",cantidad=2,
                                precio_texto=lambda:"$1.000",importe_texto=lambda:"$2.000")
        cotizacion = SimpleNamespace(codigo="COT-QA-B14",creada=timezone.now(),nombre="Cliente ficticio",correo="qa@example.invalid",telefono="",observaciones="",motivo="",
                                     get_estado_display=lambda:"Confirmada",lineas=SimpleNamespace(all=lambda:[linea]*100),total=lambda:Decimal("200000"),total_texto=lambda:"$200.000")
        inicio = perf_counter()
        pdf = construir_cotizacion(cotizacion)
        assert pdf.startswith(b"%PDF-") and len(pdf)>1000
        print(f"PDF de 100 líneas en memoria: {perf_counter()-inicio:.3f} s; {len(pdf)} bytes (medición local, no Vercel).")
        print("OK: WSGI, HTTPS, cookies, CSRF, hosts y errores con DEBUG=False; cero conexiones de BD.")


if __name__ == "__main__":
    main()
