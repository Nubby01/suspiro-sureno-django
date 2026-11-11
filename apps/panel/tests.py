from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.catalogo.models import Producto, VarianteProducto
from apps.catalogo.servicios import crear_producto_con_variante_inicial
from apps.cuentas.models import Usuario
from apps.panel.views import CatalogoInternoView, GestionView, TrabajoView

CLAVE = "una-clave-segura-19"


class PanelAccesoTests(TestCase):
    def setUp(self):
        self.administradora = Usuario.objects.create_user(
            "administra",
            "administra@example.com",
            CLAVE,
            rol=Usuario.Rol.ADMINISTRADORA,
            is_staff=False,
            is_superuser=False,
        )
        self.ayudante = Usuario.objects.create_user(
            "ayuda",
            "ayuda@example.com",
            CLAVE,
            rol=Usuario.Rol.AYUDANTE,
        )
        self.clienta = Usuario.objects.create_user(
            "ana",
            "ana@example.com",
            CLAVE,
            rol=Usuario.Rol.CLIENTE,
        )
        self.duena = get_user_model().objects.create_superuser("duena", "", CLAVE)

    def test_clienta_no_entra_a_ningun_panel(self):
        self.client.force_login(self.clienta)
        self.assertEqual(self.client.get(reverse("gestion")).status_code, 403)
        self.assertEqual(self.client.get(reverse("trabajo")).status_code, 403)

    def test_ayudante_entra_a_su_panel_y_no_al_de_administradora(self):
        self.client.force_login(self.ayudante)
        trabajo = self.client.get(reverse("trabajo"))
        self.assertEqual(trabajo.status_code, 200)
        self.assertContains(trabajo, "Área de trabajo")
        self.assertContains(trabajo, "Trabajo asignado")
        self.assertContains(trabajo, "Producción")
        self.assertContains(trabajo, reverse("trabajo_asignado"))
        self.assertNotContains(trabajo, "Personal")
        self.assertNotContains(trabajo, "Clientes")
        self.assertNotContains(trabajo, "Cotizaciones")
        self.assertNotContains(trabajo, "Inventario")
        self.assertNotContains(trabajo, "Catálogo")
        self.assertEqual(self.client.get(reverse("gestion")).status_code, 403)

    def test_administradora_entra_a_su_panel(self):
        self.client.force_login(self.administradora)
        gestion = self.client.get(reverse("gestion"))
        self.assertEqual(gestion.status_code, 200)
        for modulo in (
            "Inicio",
            "Catálogo",
            "Cotizaciones",
            "Pedidos",
            "Inventario",
            "Producción",
            "Clientes",
            "Personal",
        ):
            self.assertContains(gestion, modulo)
        self.assertNotContains(gestion, "Pendiente")
        self.assertContains(gestion, 'href="/cuenta/gestion/clientes/"')
        self.assertContains(gestion, "panel.css")
        self.assertContains(gestion, 'data-panel-toggle')
        self.assertEqual(gestion.content.decode().count("<form"), 1)
        self.assertContains(gestion, "Cerrar sesión")

    def test_superusuario_conserva_gestion_y_la_ayudante_no_ve_admin(self):
        self.client.force_login(self.duena)
        self.assertEqual(self.client.get(reverse("gestion")).status_code, 200)
        self.assertEqual(self.client.get("/admin/").status_code, 200)
        self.client.force_login(self.ayudante)
        self.assertEqual(self.client.get("/admin/").status_code, 403)

    def test_cuenta_inactiva_no_queda_dentro_del_panel(self):
        self.administradora.is_active = False
        self.administradora.save(update_fields=["is_active"])
        self.client.force_login(self.administradora)
        respuesta = self.client.get(reverse("gestion"))
        self.assertNotEqual(respuesta.status_code, 200)
        solicitud = RequestFactory().get("/cuenta/gestion/")
        solicitud.user = self.administradora
        vista = GestionView()
        vista.request = solicitud
        self.assertFalse(vista.test_func())
        solicitud.user = self.ayudante
        self.ayudante.is_active = False
        vista_trabajo = TrabajoView()
        vista_trabajo.request = solicitud
        self.assertFalse(vista_trabajo.test_func())

    def test_anonimo_va_al_ingreso_del_sitio(self):
        respuesta = self.client.get(reverse("gestion"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/cuenta/ingresar/", respuesta["Location"])

    def test_el_ingreso_sigue_llevando_al_panel_correspondiente(self):
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

    def test_la_navegacion_del_panel_se_adapta(self):
        self.client.force_login(self.administradora)
        pagina = self.client.get(reverse("gestion"))
        self.assertContains(pagina, 'aria-controls="panel-nav"')
        self.assertContains(pagina, "panel-nav--cerrado")
        css = (settings.BASE_DIR / "static" / "css" / "panel.css").read_text(encoding="utf-8")
        self.assertIn("@media (max-width: 1023px)", css)
        self.assertIn("@media (min-width: 1024px)", css)
        self.assertIn("grid-template-columns: 17rem", css)


def datos_ayudante(**extra):
    datos = {
        "first_name": "Nuria",
        "apellido_paterno": "Soto",
        "apellido_materno": "Rojas",
        "email": "nuria@example.com",
        "telefono": "+56 9 8765 4321",
        "password1": CLAVE,
        "password2": CLAVE,
    }
    datos.update(extra)
    return datos


class RegistroAyudanteTests(TestCase):
    def setUp(self):
        self.administradora = Usuario.objects.create_user(
            "administra",
            "administra@example.com",
            CLAVE,
            rol=Usuario.Rol.ADMINISTRADORA,
            is_staff=False,
            is_superuser=False,
        )
        self.ayudante = Usuario.objects.create_user(
            "ayuda",
            "ayuda@example.com",
            CLAVE,
            rol=Usuario.Rol.AYUDANTE,
        )
        self.clienta = Usuario.objects.create_user(
            "ana",
            "ana@example.com",
            CLAVE,
            rol=Usuario.Rol.CLIENTE,
        )
        self.duena = get_user_model().objects.create_superuser("duena", "", CLAVE)

    def test_administradora_ve_el_formulario(self):
        self.client.force_login(self.administradora)
        pagina = self.client.get(reverse("personal"))
        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, "Crear ayudante")
        self.assertContains(pagina, "Apellido materno")
        self.assertContains(pagina, 'href="/cuenta/gestion/personal/"')
        self.assertNotContains(pagina, "is_staff")

    def test_superusuario_tambien_puede_abrir_personal(self):
        self.client.force_login(self.duena)
        self.assertEqual(self.client.get(reverse("personal")).status_code, 200)

    def test_ayudante_clienta_y_anonimo_no_crean_cuentas(self):
        datos = datos_ayudante()
        self.client.force_login(self.ayudante)
        self.assertEqual(self.client.post(reverse("personal"), datos).status_code, 403)
        self.client.force_login(self.clienta)
        self.assertEqual(self.client.post(reverse("personal"), datos).status_code, 403)
        self.client.logout()
        anonimo = self.client.post(reverse("personal"), datos)
        self.assertEqual(anonimo.status_code, 302)
        self.assertIn("/cuenta/ingresar/", anonimo["Location"])
        self.assertFalse(Usuario.objects.filter(email="nuria@example.com").exists())

    def test_crea_ayudante_con_privilegios_fijos_y_puede_ingresar(self):
        self.client.force_login(self.administradora)
        datos = datos_ayudante(
            rol="administradora",
            is_staff="True",
            is_superuser="on",
        )
        respuesta = self.client.post(reverse("personal"), datos)
        self.assertRedirects(respuesta, reverse("personal"), fetch_redirect_response=False)
        pagina = self.client.get(reverse("personal"))
        self.assertContains(pagina, "La cuenta de ayudante de Nuria Soto Rojas quedó creada.")
        self.assertNotContains(pagina, CLAVE)
        usuario = Usuario.objects.get(email="nuria@example.com")
        self.assertEqual(usuario.first_name, "Nuria")
        self.assertEqual(usuario.last_name, "Soto Rojas")
        self.assertEqual(usuario.telefono, "+56987654321")
        self.assertEqual(usuario.rol, Usuario.Rol.AYUDANTE)
        self.assertFalse(usuario.is_staff)
        self.assertFalse(usuario.is_superuser)
        self.assertTrue(usuario.is_active)
        self.assertTrue(usuario.check_password(CLAVE))
        self.assertNotEqual(usuario.password, CLAVE)
        self.assertTrue(usuario.password.startswith("pbkdf2_"))
        self.assertEqual(usuario.groups.count(), 0)
        self.assertEqual(usuario.user_permissions.count(), 0)
        self.client.logout()
        ingreso = self.client.post(
            reverse("ingresar"),
            {"username": "Nuria@Example.com", "password": CLAVE},
        )
        self.assertRedirects(ingreso, reverse("trabajo"))

    def test_apellido_materno_puede_omitirse(self):
        self.client.force_login(self.administradora)
        self.client.post(reverse("personal"), datos_ayudante(apellido_materno=""))
        usuario = Usuario.objects.get(email="nuria@example.com")
        self.assertEqual(usuario.last_name, "Soto")

    def test_rechaza_correo_duplicado_y_datos_invalidos(self):
        self.client.force_login(self.administradora)
        self.client.post(reverse("personal"), datos_ayudante())
        repetido = self.client.post(
            reverse("personal"),
            datos_ayudante(email="  Nuria@Example.com "),
        )
        self.assertEqual(repetido.status_code, 200)
        self.assertContains(repetido, "Ya existe una cuenta con ese correo.")
        self.assertEqual(Usuario.objects.filter(email="nuria@example.com").count(), 1)
        incompleto = self.client.post(reverse("personal"), datos_ayudante(apellido_paterno=""))
        self.assertContains(incompleto, "El apellido paterno es obligatorio.")
        telefono = self.client.post(reverse("personal"), datos_ayudante(email="otra@example.com", telefono="123"))
        self.assertContains(telefono, "Ingresa un teléfono válido.")
        distinta = self.client.post(
            reverse("personal"),
            datos_ayudante(email="otra@example.com", password2=CLAVE + "-otra"),
        )
        self.assertContains(distinta, "Las contraseñas no coinciden.")
        self.assertFalse(Usuario.objects.filter(email="otra@example.com").exists())

    def test_post_sin_csrf_no_crea_la_cuenta(self):
        from django.test import Client

        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.administradora)
        respuesta = cliente.post(reverse("personal"), datos_ayudante())
        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(Usuario.objects.filter(email="nuria@example.com").exists())


def _producto(categoria, nombre, slug, precio, activo=True, referencia=""):
    return crear_producto_con_variante_inicial(
        categoria=categoria,
        nombre=nombre,
        slug=slug,
        precio=precio,
        activo=activo,
        referencia_imagen=referencia,
    )


class CatalogoInternoTests(TestCase):
    def setUp(self):
        self.administradora = Usuario.objects.create_user(
            "administra",
            "administra@example.com",
            CLAVE,
            rol=Usuario.Rol.ADMINISTRADORA,
            is_staff=False,
            is_superuser=False,
        )
        self.ayudante = Usuario.objects.create_user(
            "ayuda",
            "ayuda@example.com",
            CLAVE,
            rol=Usuario.Rol.AYUDANTE,
        )
        self.clienta = Usuario.objects.create_user(
            "ana",
            "ana@example.com",
            CLAVE,
            rol=Usuario.Rol.CLIENTE,
        )
        self.duena = get_user_model().objects.create_superuser("duena", "", CLAVE)
        from apps.catalogo.models import Categoria

        self.alfajores = Categoria.objects.create(nombre="Alfajores", slug="alfajores", orden=1)
        self.pies = Categoria.objects.create(nombre="Pies y kuchenes", slug="pies", orden=2)
        self.con_foto = _producto(
            self.alfajores,
            "Alfajor manjar",
            "alfajor-manjar",
            None,
            referencia="imagenes/catalogo-web/alfajormanjarcatalogo.jpg",
        )
        self.inactivo = _producto(
            self.pies,
            "Pie de limón",
            "pie-de-limon",
            None,
            activo=False,
        )
        self.cero = _producto(self.pies, "Porción de muestra", "porcion-muestra", 0)
        self.con_precio = _producto(self.alfajores, "Alfajor con valor", "alfajor-con-valor", Decimal("4500"))

    def _fragmento(self, respuesta, producto):
        html = respuesta.content.decode()
        inicio = html.index(f'id="producto-{producto.pk}"')
        siguiente = html.find('class="interno__fila"', inicio + 1)
        fin = siguiente if siguiente != -1 else inicio + 1200
        return html[inicio:fin]

    def test_administradora_y_superusuaria_ven_el_listado(self):
        self.client.force_login(self.administradora)
        pagina = self.client.get(reverse("catalogo_interno"))
        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, "Alfajor manjar")
        self.assertContains(pagina, "Pies y kuchenes")
        self.assertContains(pagina, "Activo")
        self.assertContains(pagina, "Inactivo")
        self.assertContains(pagina, "Consultar precio")
        self.assertContains(pagina, "/static/imagenes/catalogo-web/alfajormanjarcatalogo.jpg")
        self.assertContains(pagina, "Fotografía de Alfajor manjar")
        self.assertContains(pagina, 'href="/cuenta/gestion/catalogo/"')
        self.assertNotContains(pagina, 'href="/catalogo/"')
        self.assertContains(pagina, "4 productos")
        manjar = self._fragmento(pagina, self.con_foto)
        self.assertIn("Consultar precio", manjar)
        self.assertNotIn("$0", manjar)
        cero = self._fragmento(pagina, self.cero)
        self.assertIn("$0", cero)
        self.assertNotIn("Consultar precio", cero)
        valor = self._fragmento(pagina, self.con_precio)
        self.assertIn("$4.500", valor)
        pie = self._fragmento(pagina, self.inactivo)
        self.assertIn("Inactivo", pie)
        self.assertIn("Fotografía pendiente", pie)
        self.assertEqual(pagina.content.decode().count('method="post"'), 1)
        self.client.force_login(self.duena)
        self.assertEqual(self.client.get(reverse("catalogo_interno")).status_code, 200)

    def test_el_enlace_esta_solo_en_el_panel_de_administradora(self):
        self.client.force_login(self.administradora)
        gestion = self.client.get(reverse("gestion"))
        self.assertContains(gestion, 'href="/cuenta/gestion/catalogo/"')
        self.assertEqual(gestion.content.decode().count("<form"), 1)
        self.client.force_login(self.ayudante)
        trabajo = self.client.get(reverse("trabajo"))
        self.assertNotContains(trabajo, "Catálogo")
        self.assertNotContains(trabajo, "/cuenta/gestion/catalogo/")
        self.assertEqual(reverse("catalogo"), "/catalogo/")

    def test_ayudante_clienta_y_anonimo_no_consultan_el_catalogo(self):
        self.client.force_login(self.ayudante)
        self.assertEqual(self.client.get(reverse("catalogo_interno")).status_code, 403)
        self.assertEqual(self.client.post(reverse("catalogo_interno")).status_code, 403)
        self.client.force_login(self.clienta)
        self.assertEqual(self.client.get(reverse("catalogo_interno")).status_code, 403)
        self.client.logout()
        anonimo = self.client.get(reverse("catalogo_interno"))
        self.assertEqual(anonimo.status_code, 302)
        self.assertIn("/cuenta/ingresar/", anonimo["Location"])
        self.administradora.is_active = False
        self.administradora.save(update_fields=["is_active"])
        solicitud = RequestFactory().get("/cuenta/gestion/catalogo/")
        solicitud.user = self.administradora
        vista = CatalogoInternoView()
        vista.request = solicitud
        self.assertFalse(vista.test_func())

    def test_busqueda_y_filtro_no_alteran_los_productos(self):
        antes = list(
            Producto.objects.order_by("id").values_list(
                "id", "nombre", "activo", "referencia_imagen", "categoria_id"
            )
        )
        precios = list(
            VarianteProducto.objects.order_by("id").values_list("id", "precio", "es_predeterminada")
        )
        self.client.force_login(self.administradora)
        busqueda = self.client.get(reverse("catalogo_interno"), {"q": "  pie  "})
        self.assertContains(busqueda, "Pie de limón")
        self.assertNotContains(busqueda, "Alfajor manjar")
        self.assertContains(busqueda, "1 producto")
        self.assertContains(busqueda, "Limpiar")
        categoria = self.client.get(reverse("catalogo_interno"), {"categoria": "alfajores"})
        self.assertContains(categoria, "Alfajor manjar")
        self.assertContains(categoria, "Alfajor con valor")
        self.assertNotContains(categoria, "Pie de limón")
        self.assertNotContains(categoria, "Porción de muestra")
        ambos = self.client.get(
            reverse("catalogo_interno"),
            {"q": "MANJAR", "categoria": "alfajores"},
        )
        self.assertContains(ambos, "Alfajor manjar")
        self.assertNotContains(ambos, "Alfajor con valor")
        vacio = self.client.get(reverse("catalogo_interno"), {"q": "no-existe"})
        self.assertContains(vacio, "Ningún producto coincide con la búsqueda.")
        self.assertNotContains(vacio, "Alfajor manjar")
        rechazo = self.client.post(reverse("catalogo_interno"), {"q": "pie", "precio": "1"})
        self.assertEqual(rechazo.status_code, 405)
        self.assertEqual(
            list(
                Producto.objects.order_by("id").values_list(
                    "id", "nombre", "activo", "referencia_imagen", "categoria_id"
                )
            ),
            antes,
        )
        self.assertEqual(
            list(VarianteProducto.objects.order_by("id").values_list("id", "precio", "es_predeterminada")),
            precios,
        )
        self.assertIsNone(self.con_foto.variantes.get().precio)
        self.assertEqual(self.cero.variantes.get().precio, Decimal("0"))

    def test_sin_predeterminada_no_inventa_el_precio(self):
        huerfano = Producto.objects.create(
            categoria=self.pies,
            nombre="Masa sin precio visible",
            slug="masa-sin-precio-visible",
            activo=False,
        )
        VarianteProducto.objects.create(
            producto=huerfano,
            nombre="Otra",
            precio=Decimal("1000"),
            es_predeterminada=False,
            activa=True,
        )
        self.client.force_login(self.administradora)
        pagina = self.client.get(reverse("catalogo_interno"))
        fragmento = self._fragmento(pagina, huerfano)
        self.assertIn("Sin variante predeterminada", fragmento)
        self.assertNotIn("$1.000", fragmento)

    def test_el_listado_se_adapta_sin_desplazamiento_horizontal(self):
        css = (settings.BASE_DIR / "static" / "css" / "panel.css").read_text(encoding="utf-8")
        self.assertIn(".interno__fila", css)
        self.assertIn("minmax(0, 1fr)", css)
        self.assertIn("overflow-wrap: anywhere", css)
        self.assertIn("@media (min-width: 1024px)", css)
        self.client.force_login(self.administradora)
        pagina = self.client.get(reverse("catalogo_interno"))
        self.assertContains(pagina, "interno__fila")
        self.assertContains(pagina, "Buscar por nombre")

