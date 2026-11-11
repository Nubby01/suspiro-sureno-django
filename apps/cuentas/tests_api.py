from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework_simplejwt.tokens import AccessToken

CLAVE = "una-clave-segura-19"


class JwtTests(TestCase):
    def setUp(self):
        usuario = get_user_model()
        self.clienta = usuario.objects.create_user(
            "ana",
            "ana@example.com",
            CLAVE,
            first_name="Ana",
            last_name="Prueba",
        )
        self.otra = usuario.objects.create_user("luz", "luz@example.com", CLAVE)

    def _tokens(self, username="ana@example.com", **extra):
        datos = {"username": username, "password": CLAVE}
        datos.update(extra)
        return self.client.post(reverse("api_token"), datos)

    def test_obtiene_renueva_y_consulta_sin_exponer_la_clave(self):
        self.assertEqual(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"], timedelta(minutes=15))
        self.assertEqual(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"], timedelta(hours=12))
        respuesta = self._tokens(rol="administradora", is_superuser="1")
        self.assertEqual(respuesta.status_code, 200)
        cuerpo = respuesta.json()
        self.assertIn("access", cuerpo)
        self.assertIn("refresh", cuerpo)
        self.assertNotIn("password", cuerpo)
        self.assertNotIn(CLAVE, respuesta.content.decode())
        token = AccessToken(cuerpo["access"])
        self.assertEqual(int(token["user_id"]), self.clienta.pk)
        self.assertLessEqual(token["exp"] - token["iat"], 15 * 60)
        self.assertNotIn("password", token.payload)
        renovado = self.client.post(reverse("api_token_renovar"), {"refresh": cuerpo["refresh"]})
        self.assertEqual(renovado.status_code, 200)
        acceso = renovado.json()["access"]
        cuenta = self.client.get(reverse("api_cuenta"), HTTP_AUTHORIZATION=f"Bearer {acceso}")
        self.assertEqual(cuenta.status_code, 200)
        datos = cuenta.json()
        self.assertEqual(
            datos,
            {
                "usuario": "ana",
                "nombre": "Ana",
                "apellido": "Prueba",
                "correo": "ana@example.com",
                "rol": "cliente",
            },
        )
        self.assertNotIn("luz@example.com", cuenta.content.decode())
        self.clienta.refresh_from_db()
        self.assertEqual(self.clienta.rol, "cliente")
        self.assertFalse(self.clienta.is_superuser)
        self.assertTrue(self.clienta.password.startswith("pbkdf2_"))

    def test_rechaza_credencial_token_y_sesion_web_en_la_api(self):
        incorrecta = self.client.post(
            reverse("api_token"),
            {"username": "ana@example.com", "password": "no-es-la-clave"},
        )
        self.assertEqual(incorrecta.status_code, 401)
        self.assertContains(incorrecta, "Correo, usuario o contraseña incorrectos.", status_code=401)
        self.assertNotContains(incorrecta, "no-es-la-clave", status_code=401)
        self.clienta.is_active = False
        self.clienta.save(update_fields=["is_active"])
        inactiva = self._tokens()
        self.assertEqual(inactiva.status_code, 401)
        self.clienta.is_active = True
        self.clienta.save(update_fields=["is_active"])
        invalido = self.client.get(reverse("api_cuenta"), HTTP_AUTHORIZATION="Bearer no-es-un-token")
        self.assertEqual(invalido.status_code, 401)
        self.assertIn("válido", invalido.content.decode())
        renovacion = self.client.post(reverse("api_token_renovar"), {"refresh": "no-es-un-token"})
        self.assertEqual(renovacion.status_code, 401)
        self.assertIn("válido", renovacion.content.decode())
        self.client.force_login(self.clienta)
        sin_token = self.client.get(reverse("api_cuenta"))
        self.assertEqual(sin_token.status_code, 401)
        web = self.client.get(reverse("mi_cuenta"))
        self.assertEqual(web.status_code, 200)
        self.assertContains(web, "ana@example.com")
