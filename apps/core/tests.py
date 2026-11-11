from unittest.mock import patch
from urllib.parse import unquote

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.negocio import url_whatsapp


class ProyectoIndependienteTests(TestCase):
    def test_sqlite_es_local_y_no_apunta_al_proyecto_anterior(self):
        self.assertEqual(settings.DATABASES["default"]["ENGINE"], "django.db.backends.sqlite3")
        ajustes = (settings.BASE_DIR / "config" / "settings.py").read_text(encoding="utf-8")
        base = (settings.BASE_DIR / "config" / "base_datos.py").read_text(encoding="utf-8")
        self.assertIn("BASE_DIR / 'db.sqlite3'", ajustes)
        self.assertIn('os.environ.get("DATABASE_URL"', ajustes)
        for texto in (ajustes, base):
            self.assertNotIn("ProyectoIntegrado2", texto)
            self.assertNotIn("neon.tech", texto.lower())
            self.assertNotRegex(texto, r"postgres(?:ql)?://\S+")
        self.assertTrue(settings.CSRF_COOKIE_HTTPONLY)
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertEqual(settings.SECURE_REFERRER_POLICY, "same-origin")
        self.assertFalse(settings.SECURE_SSL_REDIRECT)

    def test_usuario_personalizado(self):
        self.assertEqual(settings.AUTH_USER_MODEL, "cuentas.Usuario")
        usuario = get_user_model()
        self.assertEqual(usuario._meta.app_label, "cuentas")
        self.assertEqual(usuario._meta.model_name, "usuario")

    def test_pagina_minima_carga_estilos(self):
        respuesta = self.client.get(reverse("inicio"))
        self.assertEqual(respuesta.status_code, 200)
        html = respuesta.content.decode()
        self.assertIn("Suspiro Sureño", html)
        self.assertIn("tokens.css", html)
        self.assertIn("DM+Sans", html)

    def test_hoja_de_tokens_existe(self):
        ruta = settings.BASE_DIR / "static" / "css" / "tokens.css"
        self.assertTrue(ruta.is_file())
        css = ruta.read_text(encoding="utf-8")
        self.assertIn("--terracota: #994215", css)
        self.assertIn("--crema: #f7f1e8", css)

    @patch.multiple("apps.core.negocio", WHATSAPP_NUMERO="56900000000", WHATSAPP_VISIBLE="+56 9 0000 0000", CORREO="contacto@example.com", INSTAGRAM="https://www.instagram.com/example/", FACEBOOK="https://www.facebook.com/example/")
    def test_el_inicio_usa_el_logo_las_fotos_y_el_contacto_oficial(self):
        html = self.client.get(reverse("inicio")).content.decode()
        self.assertIn("/static/imagenes/logo.png", html)
        self.assertIn("piedelimoninicio.png", html)
        self.assertIn("alfajorinicio.png", html)
        self.assertIn("rollosinicio.png", html)
        self.assertIn("https://www.instagram.com/example/", html)
        self.assertIn("https://www.facebook.com/example/", html)
        self.assertIn("https://wa.me/56900000000", html)
        self.assertIn("contacto@example.com", html)
        self.assertIn("Explorar catálogo", html)

    @patch.multiple("apps.core.negocio", WHATSAPP_NUMERO="56900000000", WHATSAPP_VISIBLE="+56 9 0000 0000", CORREO="contacto@example.com", INSTAGRAM="https://www.instagram.com/example/", FACEBOOK="https://www.facebook.com/example/")
    def test_whatsapp_no_lleva_datos_privados(self):
        secreto = "token-privado-de-consulta"
        url = url_whatsapp("COT-AB12", [{"nombre": "Pie de limón", "cantidad": 1}], )
        texto = unquote(url)
        self.assertTrue(url.startswith("https://wa.me/56900000000?text="))
        self.assertIn("COT-AB12", texto)
        self.assertIn("Pie de limón x 1", texto)
        self.assertNotIn(secreto, texto)
        self.assertNotIn("@", texto)
