from decimal import Decimal

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from apps.catalogo.admin import ElementoGaleriaForm, ProductoAdmin
from apps.catalogo.imagenes import PORTADA_ROLLOS, ruta_fisica, validar_referencia
from apps.catalogo.importacion import importar_catalogo
from apps.catalogo.models import Categoria, ElementoGaleria, Producto, VarianteProducto
from apps.catalogo.rollitos import cargar_rollitos
from apps.catalogo.servicios import MENSAJE_NOMBRES, MENSAJE_PRECIO_INVALIDO, crear_producto_con_variante_inicial
from apps.cuentas.models import Usuario
from apps.cuentas.servicios import normalizar_telefono

CLAVE = "una-clave-segura-19"
FOTO = "imagenes/catalogo-web/alfajormanjarcatalogo.jpg"


def _datos_producto(**extra):
    datos = {
        "nombre": "Pie de prueba",
        "descripcion": "",
        "referencia_imagen": "",
        "precio": "",
        "activo": "on",
    }
    datos.update(extra)
    return datos


def _datos_variantes(variantes, **cambios):
    datos = {
        "accion": "guardar",
        "variantes-TOTAL_FORMS": str(len(variantes)),
        "variantes-INITIAL_FORMS": str(len(variantes)),
        "variantes-MIN_NUM_FORMS": "0",
        "variantes-MAX_NUM_FORMS": "20",
    }
    for indice, variante in enumerate(variantes):
        prefijo = f"variantes-{indice}-"
        datos[prefijo + "id"] = str(variante.pk)
        datos[prefijo + "nombre"] = variante.nombre
        datos[prefijo + "precio"] = "" if variante.precio is None else format(variante.precio, "f")
        datos[prefijo + "precio_mayorista"] = (
            "" if variante.precio_mayorista is None else format(variante.precio_mayorista, "f")
        )
        datos[prefijo + "orden"] = str(variante.orden)
        if variante.activa:
            datos[prefijo + "activa"] = "on"
        if variante.es_predeterminada:
            datos[prefijo + "es_predeterminada"] = "on"
    for clave, valor in cambios.items():
        datos[clave] = valor
        if valor is None:
            datos.pop(clave)
    return datos


class EdicionCatalogoTests(TestCase):
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
        self.alfajores = Categoria.objects.create(nombre="Alfajores", slug="alfajores", orden=1)
        self.pies = Categoria.objects.create(nombre="Pies y kuchenes", slug="pies", orden=2)
        self.client.force_login(self.administradora)

    def _crear(self, **extra):
        datos = _datos_producto(categoria=str(self.alfajores.pk), **extra)
        return self.client.post(reverse("catalogo_nuevo"), datos)

    def test_crea_edita_y_desactiva_sin_eliminar(self):
        alta = self._crear(descripcion="Masa y relleno.")
        producto = Producto.objects.get(slug="pie-de-prueba")
        self.assertRedirects(alta, reverse("catalogo_editar", args=[producto.pk]))
        variante = producto.variantes.get()
        self.assertEqual(variante.nombre, "")
        self.assertIsNone(variante.precio)
        self.assertTrue(variante.es_predeterminada)
        self.assertTrue(producto.activo)
        publico = self.client.get(reverse("catalogo"))
        self.assertContains(publico, "Pie de prueba")
        self.assertContains(publico, "Consultar precio")

        edicion = self.client.post(
            reverse("catalogo_editar", args=[producto.pk]),
            {
                "nombre": "Pie de la casa",
                "descripcion": "Descripción confirmada.",
                "categoria": str(self.pies.pk),
                "referencia_imagen": FOTO,
                "activo": "on",
                "slug": "slug-manipulado",
                "precio": "99999",
            },
        )
        self.assertRedirects(edicion, reverse("catalogo_editar", args=[producto.pk]))
        producto.refresh_from_db()
        variante.refresh_from_db()
        self.assertEqual(producto.nombre, "Pie de la casa")
        self.assertEqual(producto.slug, "pie-de-prueba")
        self.assertEqual(producto.descripcion, "Descripción confirmada.")
        self.assertEqual(producto.categoria, self.pies)
        self.assertEqual(producto.referencia_imagen, FOTO)
        self.assertIsNone(variante.precio)
        self.assertEqual(Producto.objects.count(), 1)

        self.client.post(
            reverse("catalogo_editar", args=[producto.pk]),
            {
                "nombre": "Pie de la casa",
                "descripcion": "Descripción confirmada.",
                "categoria": str(self.pies.pk),
                "referencia_imagen": FOTO,
            },
        )
        producto.refresh_from_db()
        self.assertFalse(producto.activo)
        self.assertEqual(Producto.objects.count(), 1)
        self.assertEqual(producto.variantes.count(), 1)
        self.assertNotContains(self.client.get(reverse("catalogo")), "Pie de la casa")
        self.assertContains(self.client.get(reverse("catalogo_interno")), "Inactivo")

    def test_precios_variantes_y_predeterminada(self):
        self._crear()
        producto = Producto.objects.get(slug="pie-de-prueba")
        variante = producto.variantes.get()
        negativo = self.client.post(
            reverse("catalogo_variantes", args=[producto.pk]),
            _datos_variantes(producto.variantes.all(), **{"variantes-0-precio": "-1"}),
        )
        self.assertEqual(negativo.status_code, 200)
        self.assertContains(negativo, MENSAJE_PRECIO_INVALIDO)
        variante.refresh_from_db()
        self.assertIsNone(variante.precio)

        decimal = self.client.post(
            reverse("catalogo_variantes", args=[producto.pk]),
            _datos_variantes(producto.variantes.all(), **{"variantes-0-precio": "10.5"}),
        )
        self.assertContains(decimal, MENSAJE_PRECIO_INVALIDO)
        self.assertIsNone(variante.precio)

        self.client.post(
            reverse("catalogo_variantes", args=[producto.pk]),
            _datos_variantes(
                producto.variantes.all(),
                **{"variantes-0-nombre": "Unidad", "variantes-0-precio": "0"},
            ),
        )
        variante.refresh_from_db()
        self.assertEqual(variante.precio, Decimal("0"))
        self.assertEqual(variante.nombre, "Unidad")
        self.assertContains(self.client.get(reverse("catalogo_interno")), "$0")

        incompleta = self.client.post(
            reverse("catalogo_variantes", args=[producto.pk]),
            {
                "accion": "agregar",
                "nueva-nombre": "",
                "nueva-precio": "4500",
                "nueva-orden": "1",
                "nueva-activa": "on",
            },
        )
        self.assertContains(incompleta, MENSAJE_NOMBRES)
        self.assertEqual(producto.variantes.count(), 1)

        self.client.post(
            reverse("catalogo_variantes", args=[producto.pk]),
            {
                "accion": "agregar",
                "nueva-nombre": "Caja",
                "nueva-precio": "",
                "nueva-orden": "1",
                "nueva-activa": "on",
            },
        )
        self.assertEqual(producto.variantes.count(), 2)
        caja = producto.variantes.get(nombre="Caja")
        self.assertIsNone(caja.precio)
        self.assertFalse(caja.es_predeterminada)
        dos = self.client.post(
            reverse("catalogo_variantes", args=[producto.pk]),
            _datos_variantes(
                producto.variantes.order_by("orden", "id"),
                **{"variantes-1-es_predeterminada": "on"},
            ),
        )
        self.assertEqual(dos.status_code, 200)
        self.assertEqual(producto.variantes.filter(es_predeterminada=True).count(), 1)
        variante.refresh_from_db()
        self.assertTrue(variante.es_predeterminada)

        self.client.post(
            reverse("catalogo_variantes", args=[producto.pk]),
            _datos_variantes(
                producto.variantes.order_by("orden", "id"),
                **{"variantes-0-activa": None},
            ),
        )
        variante.refresh_from_db()
        self.assertTrue(variante.activa)
        self.assertTrue(Producto.objects.filter(pk=producto.pk).exists())

    def test_rechaza_fotografias_inseguras_y_acepta_la_portada_real(self):
        self._crear()
        producto = Producto.objects.get(slug="pie-de-prueba")
        for ruta in (
            "../secreto.jpg",
            "https://evil.example/foto.jpg",
            r"C:\Users\ejemplo\foto.jpg",
            "imagenes/catalogo-web/../../secreto.jpg",
            "imagenes/catalogo-web/noexiste.jpg",
        ):
            with self.subTest(ruta=ruta):
                respuesta = self.client.post(
                    reverse("catalogo_editar", args=[producto.pk]),
                    _datos_producto(
                        nombre="Pie de prueba",
                        categoria=str(self.alfajores.pk),
                        referencia_imagen=ruta,
                    ),
                )
                self.assertEqual(respuesta.status_code, 200)
                producto.refresh_from_db()
                self.assertEqual(producto.referencia_imagen, "")
        self.assertRaises(ValidationError, validar_referencia, "imagenes/../rollossabores.png")
        if ruta_fisica(PORTADA_ROLLOS):
            self.assertEqual(validar_referencia(PORTADA_ROLLOS), PORTADA_ROLLOS)
            self.assertIn(PORTADA_ROLLOS, self.client.get(reverse("catalogo_nuevo")).content.decode())

    def test_galeria_reutiliza_el_origen_y_no_lo_borra(self):
        origen = crear_producto_con_variante_inicial(
            categoria=self.alfajores,
            nombre="Rollo de canela",
            slug="rollo-de-canela",
            precio=None,
            referencia_imagen=FOTO,
        )
        self._crear(nombre="Caja de sabores")
        producto = Producto.objects.get(slug="caja-de-sabores")
        alta = self.client.post(
            reverse("catalogo_galeria", args=[producto.pk]),
            {
                "accion": "agregar",
                "sabor-producto_origen": str(origen.pk),
                "sabor-nombre": "",
                "sabor-referencia_imagen": "",
                "sabor-orden": "1",
            },
        )
        self.assertRedirects(alta, reverse("catalogo_galeria", args=[producto.pk]))
        elemento = producto.galeria.get()
        self.assertEqual(elemento.producto_origen, origen)
        self.assertEqual(elemento.referencia_imagen, "")
        self.assertEqual(elemento.nombre, "")
        pagina = self.client.get(reverse("catalogo_galeria", args=[producto.pk]))
        self.assertContains(pagina, "Rollo de canela")
        self.assertContains(pagina, FOTO)
        self.assertNotContains(pagina, "$")
        repetido = self.client.post(
            reverse("catalogo_galeria", args=[producto.pk]),
            {
                "accion": "agregar",
                "sabor-producto_origen": str(origen.pk),
                "sabor-nombre": "",
                "sabor-referencia_imagen": "",
                "sabor-orden": "2",
            },
        )
        self.assertEqual(repetido.status_code, 200)
        self.assertEqual(producto.galeria.count(), 1)
        propio = self.client.post(
            reverse("catalogo_galeria", args=[producto.pk]),
            {
                "accion": "agregar",
                "sabor-producto_origen": str(producto.pk),
                "sabor-nombre": "Mismo",
                "sabor-referencia_imagen": "",
                "sabor-orden": "3",
            },
        )
        self.assertEqual(propio.status_code, 200)
        self.assertEqual(producto.galeria.count(), 1)
        self.client.post(
            reverse("catalogo_galeria", args=[producto.pk]),
            {"accion": "quitar", "elemento": str(elemento.pk)},
        )
        self.assertEqual(producto.galeria.count(), 0)
        self.assertTrue(Producto.objects.filter(pk=origen.pk).exists())
        self.assertIsNone(origen.variantes.get().precio)
        self.assertEqual(Producto.objects.count(), 2)

    def test_los_otros_roles_no_editan_y_el_post_sin_csrf_no_cambia_nada(self):
        producto = crear_producto_con_variante_inicial(
            categoria=self.alfajores,
            nombre="Alfajor manjar",
            slug="alfajor-manjar",
            precio=None,
            referencia_imagen=FOTO,
        )
        rutas = [
            reverse("catalogo_nuevo"),
            reverse("catalogo_editar", args=[producto.pk]),
            reverse("catalogo_variantes", args=[producto.pk]),
            reverse("catalogo_galeria", args=[producto.pk]),
        ]
        for usuario in (self.ayudante, self.clienta):
            self.client.force_login(usuario)
            for ruta in rutas:
                with self.subTest(usuario=usuario.username, ruta=ruta):
                    self.assertEqual(self.client.get(ruta).status_code, 403)
                    self.assertEqual(self.client.post(ruta, {"nombre": "Cambiado"}).status_code, 403)
        self.client.logout()
        anonimo = self.client.get(reverse("catalogo_editar", args=[producto.pk]))
        self.assertEqual(anonimo.status_code, 302)
        self.assertIn("/cuenta/ingresar/", anonimo["Location"])
        producto.refresh_from_db()
        self.assertEqual(producto.nombre, "Alfajor manjar")

        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.administradora)
        rechazo = cliente.post(
            reverse("catalogo_editar", args=[producto.pk]),
            _datos_producto(nombre="Nombre robado", categoria=str(self.alfajores.pk)),
        )
        self.assertEqual(rechazo.status_code, 403)
        producto.refresh_from_db()
        self.assertEqual(producto.nombre, "Alfajor manjar")
        self.assertEqual(Producto.objects.count(), 1)

        self.administradora.is_active = False
        self.administradora.save(update_fields=["is_active"])
        self.client.force_login(self.administradora)
        rechazo_inactiva = self.client.get(reverse("catalogo_editar", args=[producto.pk]))
        self.assertEqual(rechazo_inactiva.status_code, 302)
        self.assertIn("/cuenta/ingresar/", rechazo_inactiva["Location"])
        self.assertEqual(self.client.post(reverse("catalogo_nuevo"), {"nombre": "Intruso"}).status_code, 302)
        self.assertFalse(Producto.objects.filter(nombre="Intruso").exists())

    def test_la_edicion_conserva_el_catalogo_y_la_galeria_cargados(self):
        importar_catalogo()
        cargar_rollitos()
        antes = list(
            Producto.objects.order_by("id").values_list(
                "id", "slug", "nombre", "referencia_imagen", "activo"
            )
        )
        precios = list(VarianteProducto.objects.order_by("id").values_list("id", "precio"))
        galeria = list(
            ElementoGaleria.objects.order_by("id").values_list(
                "producto__slug", "producto_origen__slug", "orden", "referencia_imagen"
            )
        )
        self.assertEqual(len(galeria), 7)
        categoria = Categoria.objects.get(slug="alfajores")
        self.client.post(
            reverse("catalogo_nuevo"),
            _datos_producto(nombre="Producto aparte", categoria=str(categoria.pk)),
        )
        self.assertTrue(Producto.objects.filter(slug="producto-aparte").exists())
        self.assertEqual(
            list(
                Producto.objects.exclude(slug="producto-aparte")
                .order_by("id")
                .values_list("id", "slug", "nombre", "referencia_imagen", "activo")
            ),
            antes,
        )
        self.assertEqual(
            list(VarianteProducto.objects.exclude(producto__slug="producto-aparte").order_by("id").values_list("id", "precio")),
            precios,
        )
        self.assertEqual(
            list(
                ElementoGaleria.objects.order_by("id").values_list(
                    "producto__slug", "producto_origen__slug", "orden", "referencia_imagen"
                )
            ),
            galeria,
        )
        self.assertEqual(Producto.objects.count(), 28)

    def test_admin_no_elimina_productos_y_valida_la_galeria(self):
        self.assertFalse(ProductoAdmin(Producto, admin.site).has_delete_permission(None))
        producto = crear_producto_con_variante_inicial(
            categoria=self.alfajores,
            nombre="Caja",
            slug="caja",
            precio=None,
        )
        formulario = ElementoGaleriaForm(
            data={
                "producto": str(producto.pk),
                "producto_origen": "",
                "nombre": "Sabor",
                "referencia_imagen": "../secreto.jpg",
                "orden": "1",
            }
        )
        self.assertFalse(formulario.is_valid())
        self.assertEqual(ElementoGaleria.objects.count(), 0)

    def test_telefono_chileno_se_normaliza_igual_en_ambos_registros(self):
        self.assertEqual(normalizar_telefono("9 1111 2222"), "+56911112222")
        self.assertEqual(normalizar_telefono("+56 9 1111 2222"), "+56911112222")
        with self.assertRaises(ValidationError):
            normalizar_telefono("9 1111 222a")
        self.client.logout()
        registro = self.client.post(
            reverse("registro"),
            {
                "first_name": "Ana",
                "last_name": "Prueba",
                "email": "  Ana.Nueva@Example.com ",
                "telefono": "9 1111 2222",
                "password1": CLAVE,
                "password2": CLAVE,
                "rol": "administradora",
                "is_staff": "True",
            },
        )
        self.assertRedirects(registro, reverse("mi_cuenta"))
        clienta = Usuario.objects.get(email="ana.nueva@example.com")
        self.assertEqual(clienta.telefono, "+56911112222")
        self.assertEqual(clienta.rol, Usuario.Rol.CLIENTE)
        self.assertFalse(clienta.is_staff)
        self.assertTrue(clienta.password.startswith("pbkdf2_"))
        self.assertNotEqual(clienta.password, CLAVE)
        self.client.logout()
        self.client.force_login(self.administradora)
        self.client.post(
            reverse("personal"),
            {
                "first_name": "Nuria",
                "apellido_paterno": "Soto",
                "apellido_materno": "",
                "email": "Nuria@Example.com",
                "telefono": "+56 9 1111 3333",
                "password1": CLAVE,
                "password2": CLAVE,
                "rol": "administradora",
                "is_superuser": "on",
            },
        )
        ayudante = Usuario.objects.get(email="nuria@example.com")
        self.assertEqual(ayudante.telefono, "+56911113333")
        self.assertEqual(ayudante.rol, Usuario.Rol.AYUDANTE)
        self.assertFalse(ayudante.is_staff)
        self.assertFalse(ayudante.is_superuser)
        self.assertTrue(ayudante.check_password(CLAVE))
        self.assertTrue(ayudante.password.startswith("pbkdf2_"))
