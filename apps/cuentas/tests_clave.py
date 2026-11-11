from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

CLAVE = "una-clave-segura-19"
NUEVA = "otra-clave-segura-20"


class CambioClaveTests(TestCase):
    def setUp(self):
        usuario = get_user_model()
        self.clienta = usuario.objects.create_user(
            "ana",
            "ana@example.com",
            CLAVE,
            first_name="Ana",
        )
        self.otra = usuario.objects.create_user(
            "luz",
            "luz@example.com",
            CLAVE,
            first_name="Luz",
        )

    def test_cambia_la_propia_clave_mantiene_la_sesion_y_guarda_hash(self):
        self.client.force_login(self.clienta)
        antes = self.clienta.password
        hash_ajena = self.otra.password
        pagina = self.client.get(reverse("cambiar_clave"))
        self.assertContains(pagina, "Contraseña actual")
        self.assertContains(pagina, "csrfmiddlewaretoken")
        self.assertNotContains(pagina, CLAVE)
        self.assertNotContains(pagina, "luz@example.com")
        respuesta = self.client.post(
            reverse("cambiar_clave"),
            {
                "old_password": CLAVE,
                "new_password1": NUEVA,
                "new_password2": NUEVA,
                "rol": "administradora",
                "usuario": str(self.otra.pk),
            },
        )
        self.assertEqual(respuesta.status_code, 302)
        cuenta = self.client.get(respuesta.url)
        self.assertEqual(cuenta.status_code, 200)
        self.assertContains(cuenta, "Tu contraseña quedó actualizada.")
        self.assertContains(cuenta, "ana@example.com")
        self.clienta.refresh_from_db()
        self.otra.refresh_from_db()
        self.assertTrue(self.clienta.password.startswith("pbkdf2_"))
        self.assertNotEqual(self.clienta.password, antes)
        self.assertNotIn(NUEVA, self.clienta.password)
        self.assertTrue(self.clienta.check_password(NUEVA))
        self.assertEqual(self.clienta.rol, "cliente")
        self.assertEqual(self.otra.password, hash_ajena)
        self.client.logout()
        self.assertTrue(self.client.login(username="ana@example.com", password=NUEVA))
        self.client.logout()
        self.assertFalse(self.client.login(username="ana@example.com", password=CLAVE))

    def test_rechaza_la_clave_actual_incorrecta(self):
        self.client.force_login(self.clienta)
        antes = self.clienta.password
        respuesta = self.client.post(
            reverse("cambiar_clave"),
            {"old_password": "no-es-la-clave", "new_password1": NUEVA, "new_password2": NUEVA},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "La contraseña actual no es correcta.")
        self.assertNotContains(respuesta, "no-es-la-clave")
        self.clienta.refresh_from_db()
        self.assertEqual(self.clienta.password, antes)

    def test_rechaza_confirmacion_distinta_y_clave_debil(self):
        self.client.force_login(self.clienta)
        antes = self.clienta.password
        distinta = self.client.post(
            reverse("cambiar_clave"),
            {"old_password": CLAVE, "new_password1": NUEVA, "new_password2": NUEVA + "x"},
        )
        self.assertContains(distinta, "Las contraseñas nuevas no coinciden.")
        debil = self.client.post(
            reverse("cambiar_clave"),
            {"old_password": CLAVE, "new_password1": "12345678", "new_password2": "12345678"},
        )
        self.assertEqual(debil.status_code, 200)
        self.assertTrue(
            any(texto in debil.content.decode() for texto in ("común", "numérica", "demasiado"))
        )
        self.clienta.refresh_from_db()
        self.assertEqual(self.clienta.password, antes)
        self.assertTrue(self.clienta.check_password(CLAVE))

    def test_sin_sesion_o_sin_csrf_no_cambia_la_clave(self):
        anonima = self.client.get(reverse("cambiar_clave"))
        self.assertRedirects(anonima, f"{reverse('ingresar')}?next={reverse('cambiar_clave')}")
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.clienta)
        antes = self.clienta.password
        respuesta = cliente.post(
            reverse("cambiar_clave"),
            {"old_password": CLAVE, "new_password1": NUEVA, "new_password2": NUEVA},
        )
        self.assertEqual(respuesta.status_code, 403)
        self.clienta.refresh_from_db()
        self.assertEqual(self.clienta.password, antes)
