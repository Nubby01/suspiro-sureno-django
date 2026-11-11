from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, RequestFactory, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.cuentas.autenticacion import CorreoOUsuarioBackend
from apps.cuentas.forms import MENSAJE_INGRESO
from apps.cuentas.models import Usuario
from apps.cuentas.servicios import MENSAJE_CORREO_REPETIDO, MENSAJE_TELEFONO

CLAVE = "una-clave-segura-19"


def datos_registro(**extra):
    datos = {
        "first_name": "Ana",
        "last_name": "Prueba",
        "email": "ana@example.com",
        "telefono": "+56 9 1234 5678",
        "password1": CLAVE,
        "password2": CLAVE,
    }
    datos.update(extra)
    return datos


class RegistroTests(TestCase):
    def test_registro_crea_cliente_y_normaliza_telefono(self):
        respuesta = self.client.post(reverse("registro"), datos_registro())
        self.assertRedirects(respuesta, reverse("mi_cuenta"))
        usuario = Usuario.objects.get(email="ana@example.com")
        self.assertEqual(usuario.rol, Usuario.Rol.CLIENTE)
        self.assertEqual(usuario.telefono, "+56912345678")
        self.assertEqual(usuario.first_name, "Ana")
        self.assertEqual(usuario.last_name, "Prueba")
        self.assertFalse(usuario.is_staff)
        self.assertFalse(usuario.is_superuser)
        self.assertEqual(usuario.groups.count(), 0)
        self.assertEqual(usuario.user_permissions.count(), 0)
        self.assertTrue(usuario.check_password(CLAVE))
        self.assertNotEqual(usuario.password, CLAVE)
        self.assertEqual(int(self.client.session["_auth_user_id"]), usuario.pk)

    def test_apellido_materno_opcional_se_guarda_en_el_apellido(self):
        respuesta = self.client.post(
            reverse("registro"),
            datos_registro(email="luz@example.com", apellido_materno="Rojas"),
        )
        self.assertRedirects(respuesta, reverse("mi_cuenta"))
        self.assertEqual(Usuario.objects.get(email="luz@example.com").last_name, "Prueba Rojas")

    def test_telefono_y_correo_son_obligatorios(self):
        sin_telefono = self.client.post(reverse("registro"), datos_registro(telefono=""))
        self.assertEqual(sin_telefono.status_code, 200)
        sin_correo = self.client.post(reverse("registro"), datos_registro(email=""))
        self.assertEqual(sin_correo.status_code, 200)
        self.assertEqual(Usuario.objects.count(), 0)

    def test_rechaza_telefono_invalido(self):
        respuesta = self.client.post(reverse("registro"), datos_registro(telefono="123"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, MENSAJE_TELEFONO)
        self.assertEqual(Usuario.objects.count(), 0)

    def test_rechaza_correo_duplicado_sin_importar_mayusculas(self):
        self.client.post(reverse("registro"), datos_registro())
        self.client.logout()
        respuesta = self.client.post(
            reverse("registro"),
            datos_registro(email="  Ana@Example.com  ", telefono="912345679"),
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, MENSAJE_CORREO_REPETIDO)
        self.assertEqual(Usuario.objects.filter(email__iexact="ana@example.com").count(), 1)

    def test_rechaza_contrasena_invalida_y_confirmacion_distinta(self):
        invalida = self.client.post(
            reverse("registro"),
            datos_registro(password1="12345678", password2="12345678"),
        )
        self.assertEqual(invalida.status_code, 200)
        distinta = self.client.post(
            reverse("registro"),
            datos_registro(password1=CLAVE, password2=CLAVE + "-otra"),
        )
        self.assertEqual(distinta.status_code, 200)
        self.assertContains(distinta, "Las contraseñas no coinciden.")
        self.assertEqual(Usuario.objects.count(), 0)

    def test_post_manipulado_no_concede_privilegios(self):
        datos = datos_registro(
            rol="administradora",
            is_staff="True",
            is_superuser="on",
            groups="1",
            user_permissions="1",
        )
        respuesta = self.client.post(reverse("registro"), datos)
        self.assertRedirects(respuesta, reverse("mi_cuenta"))
        usuario = Usuario.objects.get(email="ana@example.com")
        self.assertEqual(usuario.rol, Usuario.Rol.CLIENTE)
        self.assertFalse(usuario.is_staff)
        self.assertFalse(usuario.is_superuser)
        self.assertEqual(usuario.groups.count(), 0)
        self.assertEqual(usuario.user_permissions.count(), 0)

    def test_no_usa_un_correo_que_ya_es_nombre_de_usuario(self):
        Usuario.objects.create_user("ana@example.com", "", CLAVE)
        respuesta = self.client.post(reverse("registro"), datos_registro())
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Usuario.objects.count(), 1)
        self.assertNotIn("_auth_user_id", self.client.session)


class IngresoTests(TestCase):
    def test_las_paginas_de_acceso_conservan_campos_y_el_texto_de_bienvenida(self):
        ingreso = self.client.get(reverse("ingresar"))
        registro = self.client.get(reverse("registro"))
        self.assertContains(ingreso, "Bienvenida de nuevo")
        self.assertContains(ingreso, "Ingresa para revisar tus cotizaciones y pedidos.")
        self.assertContains(ingreso, "Correo electrónico o nombre de usuario")
        self.assertContains(ingreso, "Iniciar sesión")
        self.assertContains(ingreso, "Crear cuenta")
        self.assertContains(registro, "Crear cuenta")
        self.assertContains(registro, "Regístrate para guardar tus cotizaciones y consultar tus pedidos cuando quieras.")
        self.assertContains(registro, "Apellido materno")
        self.assertContains(registro, "(opcional)")
        self.assertNotContains(registro, "Opcional.")
        self.assertContains(registro, "Ya tengo cuenta")

    def test_cliente_ingresa_con_correo_y_superusuario_con_usuario(self):
        self.client.post(reverse("registro"), datos_registro())
        self.client.logout()
        por_correo = self.client.post(
            reverse("ingresar"),
            {"username": "Ana@Example.com", "password": CLAVE},
        )
        self.assertRedirects(por_correo, reverse("mi_cuenta"))
        self.client.logout()

        get_user_model().objects.create_superuser("duena", "", CLAVE)
        por_usuario = self.client.post(
            reverse("ingresar"),
            {"username": "duena", "password": CLAVE},
        )
        self.assertRedirects(por_usuario, reverse("gestion"))

    def test_clave_incorrecta_y_cuenta_inactiva_usan_el_mismo_mensaje(self):
        self.client.post(reverse("registro"), datos_registro())
        self.client.logout()
        incorrecta = self.client.post(
            reverse("ingresar"),
            {"username": "ana@example.com", "password": CLAVE + "-no"},
        )
        self.assertEqual(incorrecta.status_code, 200)
        self.assertContains(incorrecta, MENSAJE_INGRESO)
        self.assertNotIn("_auth_user_id", self.client.session)

        Usuario.objects.filter(email="ana@example.com").update(is_active=False)
        inactiva = self.client.post(
            reverse("ingresar"),
            {"username": "ana@example.com", "password": CLAVE},
        )
        self.assertEqual(inactiva.status_code, 200)
        self.assertContains(inactiva, MENSAJE_INGRESO)
        self.assertNotContains(inactiva, "inactiva")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_un_ingreso_fallido_no_cambia_ni_muestra_la_clave(self):
        self.client.post(reverse("registro"), datos_registro())
        usuario = Usuario.objects.get(email="ana@example.com")
        antes = usuario.password
        self.assertTrue(antes.startswith("pbkdf2_"))
        self.client.logout()
        respuesta = self.client.post(
            reverse("ingresar"),
            {"username": "ana@example.com", "password": "no-es-la-clave"},
        )
        usuario.refresh_from_db()
        self.assertEqual(usuario.password, antes)
        self.assertNotContains(respuesta, "no-es-la-clave")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_rechaza_next_externo(self):
        self.client.post(reverse("registro"), datos_registro())
        self.client.logout()
        respuesta = self.client.post(
            reverse("ingresar"),
            {
                "username": "ana@example.com",
                "password": CLAVE,
                "next": "https://example.com/fuera",
            },
        )
        self.assertRedirects(respuesta, reverse("mi_cuenta"))
        self.assertNotIn("example.com", respuesta["Location"])

    def test_texto_ambiguo_no_inicia_sesion(self):
        Usuario.objects.create_user("compartido@example.com", "", CLAVE)
        Usuario.objects.create_user("otra-cuenta", "compartido@example.com", CLAVE)
        usuario = CorreoOUsuarioBackend().authenticate(
            None,
            username="compartido@example.com",
            password=CLAVE,
        )
        self.assertIsNone(usuario)

    def test_cierre_exige_post_y_el_get_no_cierra(self):
        self.client.post(reverse("registro"), datos_registro())
        consulta = self.client.get(reverse("salir"))
        self.assertEqual(consulta.status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)
        cierre = self.client.post(reverse("salir"))
        self.assertRedirects(cierre, reverse("inicio"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_cierre_sin_csrf_no_destruye_la_sesion(self):
        usuario = Usuario.objects.create_user("ana", "ana@example.com", CLAVE)
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(usuario)
        respuesta = cliente.post(reverse("salir"))
        self.assertEqual(respuesta.status_code, 403)
        self.assertIn("_auth_user_id", cliente.session)

    def test_next_interno_legitimo_se_conserva_y_admin_se_descarta(self):
        self.client.post(reverse("registro"), datos_registro())
        self.client.logout()
        catalogo = self.client.post(
            reverse("ingresar"),
            {"username": "ana@example.com", "password": CLAVE, "next": "/catalogo/"},
        )
        self.assertRedirects(catalogo, reverse("catalogo"))
        self.client.logout()

        Usuario.objects.create_user(
            "ayuda",
            "ayuda@example.com",
            CLAVE,
            rol=Usuario.Rol.AYUDANTE,
        )
        trabajo = self.client.post(
            reverse("ingresar"),
            {"username": "ayuda", "password": CLAVE, "next": "/cuenta/trabajo/"},
        )
        self.assertRedirects(trabajo, reverse("trabajo"))
        self.client.logout()

        get_user_model().objects.create_superuser("duena", "", CLAVE)
        for destino in ("/admin/", "/admin/catalogo/producto/", "/admin/../admin/"):
            respuesta = self.client.post(
                reverse("ingresar"),
                {"username": "duena", "password": CLAVE, "next": destino},
            )
            self.assertRedirects(respuesta, reverse("gestion"))
            self.assertNotIn("/admin", respuesta["Location"])
            self.client.logout()


class PermisoTests(TestCase):
    def setUp(self):
        self.cliente = Usuario.objects.create_user(
            "ana",
            "ana@example.com",
            CLAVE,
            first_name="Ana",
            telefono="+56912345678",
        )
        self.otra = Usuario.objects.create_user(
            "bea",
            "bea@example.com",
            CLAVE,
            first_name="Bea",
            telefono="+56987654321",
        )
        self.ayudante = Usuario.objects.create_user(
            "ayuda",
            "ayuda@example.com",
            CLAVE,
            rol=Usuario.Rol.AYUDANTE,
            is_staff=True,
        )
        self.duena = Usuario.objects.create_superuser("duena", "", CLAVE)

    def test_cliente_no_entra_a_gestion_ni_admin_y_solo_ve_su_cuenta(self):
        self.client.force_login(self.cliente)
        self.assertEqual(self.client.get(reverse("gestion")).status_code, 403)
        self.assertEqual(self.client.get(reverse("trabajo")).status_code, 403)
        self.assertNotEqual(self.client.get("/admin/").status_code, 200)
        cuenta = self.client.get(reverse("mi_cuenta"))
        self.assertContains(cuenta, "ana@example.com")
        self.assertContains(cuenta, "Ana")
        self.assertNotContains(cuenta, "bea@example.com")
        self.assertEqual(self.client.get("/cuenta/2/").status_code, 404)

    def test_ayudante_entra_a_trabajo_y_no_a_gestion_ni_al_admin_de_usuarios(self):
        self.client.force_login(self.ayudante)
        self.assertEqual(self.client.get(reverse("trabajo")).status_code, 200)
        self.assertEqual(self.client.get(reverse("gestion")).status_code, 403)
        self.assertEqual(self.client.get(reverse("admin:cuentas_usuario_changelist")).status_code, 403)

    def test_superusuario_conserva_gestion_y_django_admin(self):
        self.client.force_login(self.duena)
        self.assertEqual(self.client.get(reverse("gestion")).status_code, 200)
        self.assertEqual(self.client.get("/admin/").status_code, 200)
        self.assertEqual(self.duena.rol, Usuario.Rol.ADMINISTRADORA)
        self.assertTrue(self.duena.is_superuser)
        self.assertTrue(self.duena.is_staff)

    def test_portada_y_catalogo_siguen_publicos(self):
        inicio = self.client.get(reverse("inicio"))
        catalogo = self.client.get(reverse("catalogo"))
        self.assertEqual(inicio.status_code, 200)
        self.assertEqual(catalogo.status_code, 200)
        self.assertContains(inicio, "Un dulce momento, hecho")
        self.assertContains(inicio, "Iniciar sesión")
        self.assertContains(inicio, "Crear cuenta")
        self.assertContains(catalogo, "Nuestras delicias")


class MigracionRolTests(TransactionTestCase):
    def test_asigna_administradora_sin_tocar_clave_ni_privilegios(self):
        executor = MigrationExecutor(connection)
        try:
            executor.migrate([("cuentas", "0001_initial")])
            antiguo = executor.loader.project_state([("cuentas", "0001_initial")]).apps.get_model(
                "cuentas", "Usuario"
            )
            clave = make_password("clave-que-no-cambia")
            duena = antiguo.objects.create(
                username="duena-historica",
                password=clave,
                email="",
                is_superuser=True,
                is_staff=True,
                is_active=True,
                date_joined=timezone.now(),
            )
            cliente = antiguo.objects.create(
                username="cliente-historico",
                password=make_password("otra-clave-segura"),
                email="cliente-historico@example.com",
                is_superuser=False,
                is_staff=False,
                is_active=True,
                date_joined=timezone.now(),
            )
            executor = MigrationExecutor(connection)
            executor.migrate([("cuentas", "0002_rol_telefono_correo")])
            UsuarioActual = get_user_model()
            duena_actual = UsuarioActual.objects.get(pk=duena.pk)
            cliente_actual = UsuarioActual.objects.get(pk=cliente.pk)
            self.assertEqual(duena_actual.rol, Usuario.Rol.ADMINISTRADORA)
            self.assertEqual(duena_actual.password, clave)
            self.assertEqual(duena_actual.username, "duena-historica")
            self.assertEqual(duena_actual.email, "")
            self.assertEqual(duena_actual.telefono, "")
            self.assertTrue(duena_actual.is_superuser)
            self.assertTrue(duena_actual.is_staff)
            self.assertTrue(duena_actual.is_active)
            self.assertEqual(cliente_actual.rol, Usuario.Rol.CLIENTE)
            self.assertFalse(cliente_actual.is_superuser)
            self.assertFalse(cliente_actual.is_staff)
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())


class AccesoAdminTests(TestCase):
    rutas = (
        "/admin/",
        "admin:catalogo_producto_changelist",
        "admin:catalogo_producto_add",
        "admin:password_change",
    )

    def setUp(self):
        self.superusuario = Usuario.objects.create_superuser("duena", "", CLAVE)
        self.administradora = Usuario.objects.create_user(
            "administra",
            "administra@example.com",
            CLAVE,
            rol=Usuario.Rol.ADMINISTRADORA,
            is_staff=True,
            is_superuser=False,
        )
        self.ayudante = Usuario.objects.create_user(
            "ayuda",
            "ayuda@example.com",
            CLAVE,
            rol=Usuario.Rol.AYUDANTE,
            is_staff=False,
        )
        self.ayudante_staff = Usuario.objects.create_user(
            "ayuda-staff",
            "ayuda-staff@example.com",
            CLAVE,
            rol=Usuario.Rol.AYUDANTE,
            is_staff=True,
        )
        self.clienta = Usuario.objects.create_user(
            "ana",
            "ana@example.com",
            CLAVE,
            rol=Usuario.Rol.CLIENTE,
        )

    def _rutas(self):
        for ruta in self.rutas:
            yield ruta if ruta.startswith("/") else reverse(ruta)

    def _entrar(self, usuario):
        self.client.force_login(usuario)

    def test_superusuario_activo_entra_al_indice_y_a_rutas_internas(self):
        self._entrar(self.superusuario)
        for ruta in self._rutas():
            self.assertEqual(self.client.get(ruta).status_code, 200, ruta)

    def test_administradora_sin_superusuario_recibe_403(self):
        self._entrar(self.administradora)
        for ruta in self._rutas():
            self.assertEqual(self.client.get(ruta).status_code, 403, ruta)

    def test_ayudante_sin_staff_y_con_staff_reciben_403(self):
        for usuario in (self.ayudante, self.ayudante_staff):
            self._entrar(usuario)
            for ruta in self._rutas():
                self.assertEqual(self.client.get(ruta).status_code, 403, ruta)

    def test_clienta_recibe_403(self):
        self._entrar(self.clienta)
        for ruta in self._rutas():
            self.assertEqual(self.client.get(ruta).status_code, 403, ruta)

    def test_cuentas_inactivas_no_entran(self):
        fabrica = RequestFactory()
        for usuario in (self.superusuario, self.ayudante_staff, self.administradora):
            usuario.is_active = False
            usuario.save(update_fields=["is_active"])
            self._entrar(usuario)
            for ruta in self._rutas():
                respuesta = self.client.get(ruta)
                self.assertNotEqual(respuesta.status_code, 200, ruta)
                self.assertEqual(respuesta.status_code, 302, ruta)
                self.assertIn("/admin/login/", respuesta["Location"])
            solicitud = fabrica.get("/admin/")
            solicitud.user = usuario
            self.assertFalse(admin.site.has_permission(solicitud))

    def test_anonimo_no_ve_el_mantenimiento(self):
        for ruta in self._rutas():
            respuesta = self.client.get(ruta)
            self.assertEqual(respuesta.status_code, 302, ruta)
            self.assertIn("/admin/login/", respuesta["Location"])

    def test_el_login_de_admin_no_acepta_a_quien_no_es_superusuario(self):
        respuesta = self.client.post(
            reverse("admin:login"),
            {"username": "ayuda-staff", "password": CLAVE, "next": "/admin/"},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertContains(respuesta, "No se pudo iniciar sesión en el mantenimiento.")

    def test_el_ingreso_del_sitio_sigue_redirigiendo_segun_el_rol(self):
        clienta = self.client.post(
            reverse("ingresar"),
            {"username": "ana@example.com", "password": CLAVE},
        )
        self.assertRedirects(clienta, reverse("mi_cuenta"))
        self.client.logout()
        ayuda = self.client.post(
            reverse("ingresar"),
            {"username": "ayuda", "password": CLAVE},
        )
        self.assertRedirects(ayuda, reverse("trabajo"))
        self.client.logout()
        duena = self.client.post(
            reverse("ingresar"),
            {"username": "duena", "password": CLAVE},
        )
        self.assertRedirects(duena, reverse("gestion"))


class MiCuentaEdicionTests(TestCase):
    def setUp(self):
        self.clienta = Usuario.objects.create_user(
            "ana",
            "ana@example.com",
            CLAVE,
            first_name="Ana",
            last_name="Soto",
            rol=Usuario.Rol.CLIENTE,
            telefono="+56912345678",
        )
        self.ayudante = Usuario.objects.create_user(
            "ayuda",
            "ayuda@example.com",
            CLAVE,
            rol=Usuario.Rol.AYUDANTE,
        )
        self.duena = Usuario.objects.create_superuser("duena", "", CLAVE)

    def test_cada_rol_abre_mi_cuenta_y_no_cambia_sus_permisos(self):
        for usuario in (self.clienta, self.ayudante, self.duena):
            self.client.force_login(usuario)
            pagina = self.client.get(reverse("mi_cuenta"))
            self.assertEqual(pagina.status_code, 200)
            self.assertContains(pagina, "Datos personales")
            self.assertContains(pagina, "Seguridad")
            self.assertContains(pagina, "(opcional)")
            self.assertNotContains(pagina, "Opcional.")
            rol = usuario.rol
            staff = usuario.is_staff
            superusuario = usuario.is_superuser
            respuesta = self.client.post(
                reverse("mi_cuenta"),
                {
                    "accion": "datos",
                    "first_name": "Ana",
                    "apellido_paterno": "Soto",
                    "apellido_materno": "Rojas",
                    "email": usuario.email,
                    "telefono": "+56912345678",
                    "rol": "administradora",
                    "is_staff": "1",
                    "is_superuser": "1",
                },
            )
            self.assertRedirects(respuesta, reverse("mi_cuenta"))
            usuario.refresh_from_db()
            self.assertEqual(usuario.last_name, "Soto Rojas")
            self.assertEqual(usuario.rol, rol)
            self.assertEqual(usuario.is_staff, staff)
            self.assertEqual(usuario.is_superuser, superusuario)
            self.client.logout()

    def test_el_cambio_de_clave_en_mi_cuenta_mantiene_la_sesion(self):
        self.client.force_login(self.clienta)
        respuesta = self.client.post(
            reverse("mi_cuenta"),
            {
                "accion": "clave",
                "old_password": CLAVE,
                "new_password1": "otra-clave-segura-20",
                "new_password2": "otra-clave-segura-20",
            },
        )
        self.assertRedirects(respuesta, reverse("mi_cuenta"))
        self.assertEqual(self.client.get(reverse("mi_cuenta")).status_code, 200)
        self.clienta.refresh_from_db()
        self.assertTrue(self.clienta.check_password("otra-clave-segura-20"))

    def test_una_ayudante_no_consulta_clientas(self):
        self.client.force_login(self.ayudante)
        self.assertEqual(self.client.get(reverse("clientes_gestion")).status_code, 403)
        self.assertEqual(self.client.get(reverse("cliente_detalle", args=[self.clienta.pk])).status_code, 403)
