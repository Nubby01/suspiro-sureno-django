import tempfile
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.test.utils import CaptureQueriesContext
from django.db.models.deletion import ProtectedError
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.catalogo.consultas import catalogo_publico, formato_clp
from apps.catalogo.imagenes import MENSAJE_AUSENTE, MENSAJE_RUTA
from apps.catalogo.models import Categoria, Producto, VarianteProducto
from apps.catalogo.servicios import (
    MENSAJE_DOS_PREDETERMINADAS,
    MENSAJE_NOMBRES,
    MENSAJE_NOMBRES_REPETIDOS,
    MENSAJE_PRECIO,
    MENSAJE_PUBLICACION,
    agregar_variante,
    cambiar_variante_predeterminada,
    crear_producto_con_variante_inicial,
    desactivar_variante,
    validar_producto_para_venta,
)


class CatalogoModelosTests(TestCase):
    def setUp(self):
        self.categoria = Categoria.objects.create(nombre="Kuchen", slug="kuchen", orden=1)

    def test_crear_categoria_valida(self):
        categoria = Categoria(nombre="Rollitos", slug="rollitos", descripcion="Porción", orden=2)
        categoria.full_clean()
        categoria.save()

        self.assertTrue(categoria.activa)
        self.assertEqual(str(categoria), "Rollitos")
        self.assertEqual(list(Categoria.objects.values_list("slug", flat=True)), ["kuchen", "rollitos"])

    def test_producto_inicial_guarda_el_precio_solo_en_la_variante(self):
        producto = crear_producto_con_variante_inicial(
            categoria=self.categoria,
            nombre="Kuchen de prueba",
            slug="kuchen-de-prueba",
            precio=Decimal("4500"),
        )

        self.assertFalse(any(campo.name == "precio" for campo in Producto._meta.fields))
        self.assertFalse(any(campo.name == "es_simple" for campo in Producto._meta.fields))
        variante = producto.variantes.get()
        self.assertEqual(variante.precio, Decimal("4500"))
        self.assertTrue(variante.es_predeterminada)
        self.assertTrue(variante.activa)
        self.assertEqual(variante.nombre, "")
        self.assertEqual(str(variante), "Kuchen de prueba")

    def test_varias_variantes_con_precios_distintos(self):
        producto = crear_producto_con_variante_inicial(
            categoria=self.categoria,
            nombre="Berlín de prueba",
            slug="berlin-de-prueba",
            precio=Decimal("1500"),
            nombre_variante="Crema",
        )
        agregar_variante(producto=producto, nombre="Manjar", precio=Decimal("1800"))

        precios = set(producto.variantes.values_list("precio", flat=True))
        self.assertEqual(precios, {Decimal("1500"), Decimal("1800")})
        self.assertEqual(producto.variantes.filter(es_predeterminada=True).count(), 1)

    def test_rechaza_precio_negativo_en_la_operacion_y_en_la_base(self):
        with self.assertRaises(ValidationError) as error:
            crear_producto_con_variante_inicial(
                categoria=self.categoria,
                nombre="Precio inválido",
                slug="precio-invalido",
                precio=Decimal("-1"),
            )
        self.assertIn(MENSAJE_PRECIO, error.exception.messages)
        self.assertEqual(Producto.objects.count(), 0)
        self.assertEqual(VarianteProducto.objects.count(), 0)

        producto = crear_producto_con_variante_inicial(
            categoria=self.categoria,
            nombre="Base de precio",
            slug="base-de-precio",
            precio=Decimal("1000"),
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                VarianteProducto.objects.create(
                    producto=producto,
                    nombre="Negativa",
                    precio=Decimal("-5"),
                    es_predeterminada=False,
                )

    def test_precio_pendiente_se_distingue_de_cero_y_permite_publicar(self):
        confirmado = crear_producto_con_variante_inicial(
            categoria=self.categoria,
            nombre="Precio cero",
            slug="precio-cero",
            precio=0,
            nombre_variante="Unidad",
        )
        cero = confirmado.variantes.get()
        self.assertEqual(cero.precio, Decimal("0"))
        pendiente = crear_producto_con_variante_inicial(
            categoria=self.categoria,
            nombre="Precio por consultar",
            slug="precio-por-consultar",
            precio=None,
            activo=True,
        )
        self.assertIsNone(pendiente.variantes.get().precio)
        self.assertTrue(pendiente.activo)
        self.assertNotEqual(pendiente.variantes.get().precio, cero.precio)

    def test_rechaza_dos_predeterminadas_del_mismo_producto(self):
        producto = crear_producto_con_variante_inicial(
            categoria=self.categoria,
            nombre="Torta de prueba",
            slug="torta-de-prueba",
            precio=Decimal("9000"),
            nombre_variante="Chocolate",
        )
        segunda = VarianteProducto(
            producto=producto,
            nombre="Frambuesa",
            precio=Decimal("9500"),
            es_predeterminada=True,
        )
        with self.assertRaises(ValidationError) as error:
            segunda.full_clean()
        self.assertIn("predeterminada", " ".join(error.exception.messages))
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                VarianteProducto.objects.bulk_create([segunda])

    def test_cambiar_la_predeterminada_deja_una_sola(self):
        producto = crear_producto_con_variante_inicial(
            categoria=self.categoria,
            nombre="Pie de prueba",
            slug="pie-de-prueba",
            precio=Decimal("7000"),
            nombre_variante="Limón",
        )
        nueva = agregar_variante(producto=producto, nombre="Manzana", precio=Decimal("7200"))
        cambiar_variante_predeterminada(nueva)

        predeterminada = producto.variantes.get(es_predeterminada=True)
        self.assertEqual(predeterminada.pk, nueva.pk)
        self.assertEqual(producto.variantes.filter(es_predeterminada=True).count(), 1)
        self.assertTrue(predeterminada.activa)

    def test_rechaza_nombres_duplicados_o_vacios_cuando_hay_varias(self):
        producto = crear_producto_con_variante_inicial(
            categoria=self.categoria,
            nombre="Alfajor de prueba",
            slug="alfajor-de-prueba",
            precio=Decimal("1200"),
            nombre_variante="Chocolate",
        )
        with self.assertRaises(ValidationError) as repetido:
            agregar_variante(producto=producto, nombre="chocolate", precio=Decimal("1300"))
        self.assertTrue(
            MENSAJE_NOMBRES_REPETIDOS in repetido.exception.messages
            or any("nombre" in mensaje.lower() for mensaje in repetido.exception.messages)
        )
        self.assertEqual(producto.variantes.count(), 1)

        simple = crear_producto_con_variante_inicial(
            categoria=self.categoria,
            nombre="Simple sin nombre",
            slug="simple-sin-nombre",
            precio=Decimal("1000"),
        )
        with self.assertRaises(ValidationError) as vacio:
            agregar_variante(producto=simple, nombre="Nuevo sabor", precio=Decimal("1100"))
        self.assertIn(MENSAJE_NOMBRES, vacio.exception.messages)
        self.assertEqual(simple.variantes.count(), 1)

    def test_rechaza_publicar_sin_variante_activa_predeterminada(self):
        producto = crear_producto_con_variante_inicial(
            categoria=self.categoria,
            nombre="Sin venta",
            slug="sin-venta",
            precio=Decimal("2000"),
            activo=False,
        )
        variante = producto.variantes.get()
        variante.activa = False
        variante.save(update_fields=["activa"])
        producto.activo = True
        producto.save(update_fields=["activo"])

        with self.assertRaises(ValidationError) as error:
            validar_producto_para_venta(producto)
        self.assertIn(MENSAJE_PUBLICACION, error.exception.messages)

    def test_desactivar_variante_conserva_el_registro(self):
        producto = crear_producto_con_variante_inicial(
            categoria=self.categoria,
            nombre="Dos sabores",
            slug="dos-sabores",
            precio=Decimal("2000"),
            nombre_variante="Nuez",
        )
        segunda = agregar_variante(producto=producto, nombre="Coco", precio=Decimal("2100"))
        desactivar_variante(segunda)

        segunda.refresh_from_db()
        self.assertFalse(segunda.activa)
        self.assertTrue(VarianteProducto.objects.filter(pk=segunda.pk).exists())

    def test_no_desactiva_la_unica_variante_de_un_producto_publicado(self):
        producto = crear_producto_con_variante_inicial(
            categoria=self.categoria,
            nombre="Única vendible",
            slug="unica-vendible",
            precio=Decimal("3000"),
        )
        variante = producto.variantes.get()
        with self.assertRaises(ValidationError) as error:
            desactivar_variante(variante)
        self.assertIn(MENSAJE_PUBLICACION, error.exception.messages)
        variante.refresh_from_db()
        self.assertTrue(variante.activa)

    def test_no_elimina_categoria_con_productos_ni_producto_con_variantes(self):
        producto = crear_producto_con_variante_inicial(
            categoria=self.categoria,
            nombre="Protegido",
            slug="protegido",
            precio=Decimal("1000"),
        )
        with self.assertRaises(ProtectedError):
            self.categoria.delete()
        with self.assertRaises(ProtectedError):
            producto.delete()
        self.assertTrue(Categoria.objects.filter(pk=self.categoria.pk).exists())
        self.assertTrue(Producto.objects.filter(pk=producto.pk).exists())

    def test_slugs_son_unicos(self):
        with self.assertRaises(ValidationError):
            repetida = Categoria(nombre="Otra", slug="kuchen")
            repetida.full_clean()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Categoria.objects.create(nombre="Otra", slug="kuchen")

        crear_producto_con_variante_inicial(
            categoria=self.categoria,
            nombre="Primero",
            slug="mismo-slug",
            precio=Decimal("1000"),
        )
        with self.assertRaises(ValidationError):
            crear_producto_con_variante_inicial(
                categoria=self.categoria,
                nombre="Segundo",
                slug="mismo-slug",
                precio=Decimal("1000"),
            )
        self.assertEqual(Producto.objects.filter(slug="mismo-slug").count(), 1)

    def test_portada_y_usuario_no_regresan(self):
        self.assertEqual(settings.AUTH_USER_MODEL, "cuentas.Usuario")
        self.assertEqual(get_user_model()._meta.model_name, "usuario")
        respuesta = self.client.get(reverse("inicio"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Suspiro Sureño")


class CatalogoAdminTests(TestCase):
    def setUp(self):
        usuario = get_user_model().objects.create_superuser(
            username="auditor",
            email="auditor@example.com",
            password="una-clave-larga-1",
        )
        self.client.force_login(usuario)
        self.categoria = Categoria.objects.create(nombre="Pies", slug="pies")

    def _datos_variante(self, indice, **extra):
        datos = {
            f"variantes-{indice}-nombre": "",
            f"variantes-{indice}-precio": "2500",
            f"variantes-{indice}-orden": "0",
            f"variantes-{indice}-id": "",
            f"variantes-{indice}-producto": "",
        }
        datos.update(extra)
        return datos

    def _gestion(self, total, inicial=0):
        return {
            "variantes-TOTAL_FORMS": str(total),
            "variantes-INITIAL_FORMS": str(inicial),
            "variantes-MIN_NUM_FORMS": "0",
            "variantes-MAX_NUM_FORMS": "1000",
        }

    def test_admin_crea_categoria_y_producto_con_variante(self):
        alta_categoria = self.client.post(
            reverse("admin:catalogo_categoria_add"),
            {"nombre": "Rollitos", "slug": "rollitos", "descripcion": "", "orden": "3", "activa": "on"},
        )
        self.assertEqual(alta_categoria.status_code, 302)
        self.assertTrue(Categoria.objects.filter(slug="rollitos").exists())

        datos = {
            "categoria": str(self.categoria.pk),
            "nombre": "Pie de limón de prueba",
            "slug": "pie-de-limon-de-prueba",
            "descripcion": "",
            "referencia_imagen": "",
            "activo": "on",
            **self._gestion(1),
            **self._datos_variante(0, **{"variantes-0-es_predeterminada": "on", "variantes-0-activa": "on"}),
        }
        alta_producto = self.client.post(reverse("admin:catalogo_producto_add"), datos)
        self.assertEqual(alta_producto.status_code, 302, alta_producto.content[:1500])
        producto = Producto.objects.get(slug="pie-de-limon-de-prueba")
        self.assertEqual(producto.variantes.count(), 1)
        self.assertTrue(producto.variantes.get().es_predeterminada)

    def test_admin_rechaza_precio_negativo_dos_predeterminadas_y_producto_sin_variante(self):
        base = {
            "categoria": str(self.categoria.pk),
            "nombre": "Rechazado",
            "slug": "rechazado",
            "descripcion": "",
            "referencia_imagen": "",
            "activo": "on",
        }
        negativo = self.client.post(
            reverse("admin:catalogo_producto_add"),
            {**base, **self._gestion(1), **self._datos_variante(0, **{"variantes-0-precio": "-10", "variantes-0-es_predeterminada": "on", "variantes-0-activa": "on"})},
        )
        self.assertEqual(negativo.status_code, 200)
        self.assertFalse(Producto.objects.filter(slug="rechazado").exists())

        dos = self.client.post(
            reverse("admin:catalogo_producto_add"),
            {
                **base,
                "slug": "dos-marcas",
                **self._gestion(2),
                **self._datos_variante(0, **{"variantes-0-nombre": "Uno", "variantes-0-es_predeterminada": "on", "variantes-0-activa": "on"}),
                **self._datos_variante(1, **{"variantes-1-nombre": "Dos", "variantes-1-precio": "2600", "variantes-1-es_predeterminada": "on", "variantes-1-activa": "on"}),
            },
        )
        self.assertEqual(dos.status_code, 200)
        self.assertContains(dos, MENSAJE_DOS_PREDETERMINADAS)
        self.assertFalse(Producto.objects.filter(slug="dos-marcas").exists())

        sin_variante = self.client.post(
            reverse("admin:catalogo_producto_add"),
            {**base, "slug": "sin-variante", **self._gestion(0)},
        )
        self.assertEqual(sin_variante.status_code, 200)
        self.assertContains(sin_variante, MENSAJE_PUBLICACION)
        self.assertFalse(Producto.objects.filter(slug="sin-variante").exists())

    def test_admin_edita_nombre_y_descripcion_de_categoria(self):
        edicion = self.client.post(
            reverse("admin:catalogo_categoria_change", args=[self.categoria.pk]),
            {
                "nombre": "Pies de prueba",
                "slug": self.categoria.slug,
                "descripcion": "Descripción editada en el admin",
                "orden": "0",
                "activa": "on",
            },
        )
        self.assertEqual(edicion.status_code, 302, edicion.content[:1500])
        self.categoria.refresh_from_db()
        self.assertEqual(self.categoria.nombre, "Pies de prueba")
        self.assertEqual(self.categoria.descripcion, "Descripción editada en el admin")
        self.assertTrue(self.categoria.activa)

    def test_admin_desactiva_categoria_sin_eliminarla(self):
        identificador = self.categoria.pk
        baja = self.client.post(
            reverse("admin:catalogo_categoria_change", args=[identificador]),
            {
                "nombre": self.categoria.nombre,
                "slug": self.categoria.slug,
                "descripcion": self.categoria.descripcion,
                "orden": "0",
            },
        )
        self.assertEqual(baja.status_code, 302, baja.content[:1500])
        self.categoria.refresh_from_db()
        self.assertFalse(self.categoria.activa)
        self.assertTrue(Categoria.objects.filter(pk=identificador).exists())

    def test_admin_edita_producto_y_conserva_su_variante(self):
        otra = Categoria.objects.create(nombre="Kuchen", slug="kuchen")
        producto = crear_producto_con_variante_inicial(
            categoria=self.categoria,
            nombre="Kuchen de prueba",
            slug="kuchen-de-prueba",
            descripcion="Antes",
            precio=Decimal("4500"),
            nombre_variante="Nuez",
        )
        variante = producto.variantes.get()
        pagina = self.client.get(reverse("admin:catalogo_producto_change", args=[producto.pk]))
        self.assertEqual(pagina.status_code, 200)
        self.assertNotContains(pagina, 'name="precio"')
        self.assertContains(pagina, "variantes-0-precio")

        edicion = self.client.post(
            reverse("admin:catalogo_producto_change", args=[producto.pk]),
            {
                "categoria": str(otra.pk),
                "nombre": "Kuchen editado",
                "slug": producto.slug,
                "descripcion": "Después",
                "referencia_imagen": "",
                "activo": "on",
                **self._gestion(1, inicial=1),
                "variantes-0-id": str(variante.pk),
                "variantes-0-nombre": variante.nombre,
                "variantes-0-precio": "4500",
                "variantes-0-orden": "0",
                "variantes-0-es_predeterminada": "on",
                "variantes-0-activa": "on",
            },
        )
        self.assertEqual(edicion.status_code, 302, edicion.content[:1500])
        producto.refresh_from_db()
        variante.refresh_from_db()
        self.assertEqual(producto.nombre, "Kuchen editado")
        self.assertEqual(producto.descripcion, "Después")
        self.assertEqual(producto.categoria_id, otra.pk)
        self.assertFalse(any(campo.name == "precio" for campo in Producto._meta.fields))
        self.assertEqual(producto.variantes.count(), 1)
        self.assertEqual(variante.precio, Decimal("4500"))
        self.assertTrue(variante.es_predeterminada)

    def test_admin_cambia_la_variante_predeterminada(self):
        producto = crear_producto_con_variante_inicial(
            categoria=self.categoria,
            nombre="Berlín de prueba",
            slug="berlin-de-prueba",
            precio=Decimal("1500"),
            nombre_variante="Crema",
        )
        crema = producto.variantes.get()
        manjar = agregar_variante(
            producto=producto,
            nombre="Manjar",
            precio=Decimal("1800"),
            orden=1,
        )
        cambio = self.client.post(
            reverse("admin:catalogo_producto_change", args=[producto.pk]),
            {
                "categoria": str(self.categoria.pk),
                "nombre": producto.nombre,
                "slug": producto.slug,
                "descripcion": "",
                "referencia_imagen": "",
                "activo": "on",
                **self._gestion(2, inicial=2),
                "variantes-0-id": str(crema.pk),
                "variantes-0-nombre": "Crema",
                "variantes-0-precio": "1500",
                "variantes-0-orden": "0",
                "variantes-0-activa": "on",
                "variantes-1-id": str(manjar.pk),
                "variantes-1-nombre": "Manjar",
                "variantes-1-precio": "1800",
                "variantes-1-orden": "1",
                "variantes-1-es_predeterminada": "on",
                "variantes-1-activa": "on",
            },
        )
        self.assertEqual(cambio.status_code, 302, cambio.content[:1500])
        predeterminada = producto.variantes.get(es_predeterminada=True)
        self.assertEqual(predeterminada.pk, manjar.pk)
        self.assertEqual(producto.variantes.filter(es_predeterminada=True).count(), 1)
        self.assertEqual(
            set(producto.variantes.values_list("precio", flat=True)),
            {Decimal("1500"), Decimal("1800")},
        )

    def _directorio_estatico(self, nombre="pieprueba.jpg", ancho=1280, alto=853):
        directorio = tempfile.TemporaryDirectory()
        self.addCleanup(directorio.cleanup)
        destino = Path(directorio.name) / "imagenes" / "catalogo-web" / nombre
        destino.parent.mkdir(parents=True)
        alto_bytes = alto.to_bytes(2, "big")
        ancho_bytes = ancho.to_bytes(2, "big")
        destino.write_bytes(
            b"\xff\xd8\xff\xc0\x00\x0b\x08"
            + alto_bytes
            + ancho_bytes
            + b"\x01\x01\x11\x00\xff\xd9"
        )
        return directorio.name

    def test_admin_ofrece_fotografias_optimizadas_y_permite_dejarlas_vacias(self):
        pagina = self.client.get(reverse("admin:catalogo_producto_add"))
        self.assertContains(pagina, "Sin fotografía")
        self.assertContains(pagina, "imagenes/catalogo-web/rollopizzacatalogo.jpg")
        self.assertNotContains(pagina, "logo.png")
        self.assertNotContains(pagina, "inicio.png")

    def test_admin_guarda_una_ruta_relativa_segura(self):
        raiz = self._directorio_estatico()
        ruta = "imagenes/catalogo-web/pieprueba.jpg"
        with override_settings(STATICFILES_DIRS=[raiz]):
            alta = self.client.post(
                reverse("admin:catalogo_producto_add"),
                {
                    "categoria": str(self.categoria.pk),
                    "nombre": "Pie con fotografía",
                    "slug": "pie-con-fotografia",
                    "descripcion": "",
                    "referencia_imagen": ruta,
                    "activo": "on",
                    **self._gestion(1),
                    **self._datos_variante(
                        0,
                        **{"variantes-0-es_predeterminada": "on", "variantes-0-activa": "on"},
                    ),
                },
            )
        self.assertEqual(alta.status_code, 302, alta.content[:1500])
        producto = Producto.objects.get(slug="pie-con-fotografia")
        self.assertEqual(producto.referencia_imagen, ruta)
        self.assertTrue(producto.activo)
        self.assertEqual(producto.variantes.get().precio, Decimal("2500"))

    def test_admin_rechaza_rutas_externas_absolutas_y_ausentes(self):
        peligrosas = [
            "https://evil.example/a.jpg",
            "http://127.0.0.1/a.jpg",
            "//evil.example/a.jpg",
            r"C:\imagenes\a.jpg",
            "/imagenes/catalogo-web/a.jpg",
            "imagenes/catalogo-web/../secreto.jpg",
            "imagenes/catalogo-web/pie pru.jpg",
            "imagenes/inicio/alfajorinicio.png",
            "imagenes/catalogo-web/logo.png",
        ]
        for ruta in peligrosas:
            with self.subTest(ruta=ruta):
                respuesta = self.client.post(
                    reverse("admin:catalogo_producto_add"),
                    {
                        "categoria": str(self.categoria.pk),
                        "nombre": "Ruta rechazada",
                        "slug": "ruta-rechazada",
                        "descripcion": "",
                        "referencia_imagen": ruta,
                        "activo": "on",
                        **self._gestion(1),
                        **self._datos_variante(
                            0,
                            **{
                                "variantes-0-es_predeterminada": "on",
                                "variantes-0-activa": "on",
                            },
                        ),
                    },
                )
                self.assertEqual(respuesta.status_code, 200)
                self.assertContains(respuesta, MENSAJE_RUTA)
                self.assertFalse(Producto.objects.filter(slug="ruta-rechazada").exists())

        raiz = self._directorio_estatico()
        with override_settings(STATICFILES_DIRS=[raiz]):
            ausente = self.client.post(
                reverse("admin:catalogo_producto_add"),
                {
                    "categoria": str(self.categoria.pk),
                    "nombre": "Ruta ausente",
                    "slug": "ruta-ausente",
                    "descripcion": "",
                    "referencia_imagen": "imagenes/catalogo-web/noexiste.jpg",
                    "activo": "on",
                    **self._gestion(1),
                    **self._datos_variante(
                        0,
                        **{"variantes-0-es_predeterminada": "on", "variantes-0-activa": "on"},
                    ),
                },
            )
        self.assertEqual(ausente.status_code, 200)
        self.assertContains(ausente, MENSAJE_AUSENTE)
        self.assertFalse(Producto.objects.filter(slug="ruta-ausente").exists())

    def test_admin_con_fotografia_sigue_exigiendo_variante_publicable(self):
        raiz = self._directorio_estatico()
        with override_settings(STATICFILES_DIRS=[raiz]):
            respuesta = self.client.post(
                reverse("admin:catalogo_producto_add"),
                {
                    "categoria": str(self.categoria.pk),
                    "nombre": "Sin variante y con foto",
                    "slug": "sin-variante-con-foto",
                    "descripcion": "",
                    "referencia_imagen": "imagenes/catalogo-web/pieprueba.jpg",
                    "activo": "on",
                    **self._gestion(0),
                },
            )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, MENSAJE_PUBLICACION)
        self.assertFalse(Producto.objects.filter(slug="sin-variante-con-foto").exists())

    def test_admin_guarda_precio_pendiente_y_no_lo_convierte_en_cero(self):
        alta = self.client.post(
            reverse("admin:catalogo_producto_add"),
            {
                "categoria": str(self.categoria.pk),
                "nombre": "Precio por consultar",
                "slug": "precio-por-consultar-admin",
                "descripcion": "",
                "referencia_imagen": "",
                "activo": "on",
                **self._gestion(1),
                **self._datos_variante(
                    0,
                    **{
                        "variantes-0-precio": "",
                        "variantes-0-es_predeterminada": "on",
                        "variantes-0-activa": "on",
                    },
                ),
            },
        )
        self.assertEqual(alta.status_code, 302, alta.content[:1500])
        variante = Producto.objects.get(slug="precio-por-consultar-admin").variantes.get()
        self.assertIsNone(variante.precio)
        self.assertTrue(variante.activa)
        self.assertTrue(variante.es_predeterminada)
        listado = self.client.get(reverse("admin:catalogo_varianteproducto_changelist"))
        self.assertContains(listado, "Consultar precio")

        cero = self.client.post(
            reverse("admin:catalogo_producto_add"),
            {
                "categoria": str(self.categoria.pk),
                "nombre": "Precio cero admin",
                "slug": "precio-cero-admin",
                "descripcion": "",
                "referencia_imagen": "",
                "activo": "on",
                **self._gestion(1),
                **self._datos_variante(
                    0,
                    **{
                        "variantes-0-precio": "0",
                        "variantes-0-es_predeterminada": "on",
                        "variantes-0-activa": "on",
                    },
                ),
            },
        )
        self.assertEqual(cero.status_code, 302, cero.content[:1500])
        self.assertEqual(
            Producto.objects.get(slug="precio-cero-admin").variantes.get().precio,
            Decimal("0"),
        )


class CatalogoPublicoTests(TestCase):
    def setUp(self):
        self.categoria = Categoria.objects.create(
            nombre="Pies de prueba",
            slug="pies-de-prueba",
            descripcion="Horneados de prueba",
            orden=1,
        )

    def _publicado(self, **extra):
        datos = {
            "categoria": self.categoria,
            "nombre": "Pie de prueba",
            "slug": "pie-de-prueba",
            "descripcion": "Descripción visible de prueba",
            "precio": Decimal("4500"),
        }
        datos.update(extra)
        return crear_producto_con_variante_inicial(**datos)

    def test_ruta_publica_responde_con_el_catalogo_vacio(self):
        respuesta = self.client.get(reverse("catalogo"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Nuestras delicias")
        self.assertContains(respuesta, "Todavía no hay productos publicados")
        self.assertContains(respuesta, "catalogo.css")
        self.assertContains(respuesta, "catalogo.js")
        self.assertNotContains(respuesta, "Alfajor de muestra")
        self.assertNotContains(respuesta, "No está a la venta")
        self.assertNotContains(respuesta, "Cotizar")

    def test_oculta_categoria_inactiva_producto_inactivo_y_sin_variante_vendible(self):
        self._publicado()
        inactiva = Categoria.objects.create(
            nombre="Categoría inactiva",
            slug="categoria-inactiva",
            activa=False,
        )
        crear_producto_con_variante_inicial(
            categoria=inactiva,
            nombre="Producto de categoría inactiva",
            slug="producto-categoria-inactiva",
            precio=Decimal("1000"),
        )
        crear_producto_con_variante_inicial(
            categoria=self.categoria,
            nombre="Producto inactivo",
            slug="producto-inactivo",
            precio=Decimal("1000"),
            activo=False,
        )
        sin_venta = Producto.objects.create(
            categoria=self.categoria,
            nombre="Producto sin variante vendible",
            slug="producto-sin-variante-vendible",
            activo=True,
        )
        VarianteProducto.objects.create(
            producto=sin_venta,
            nombre="",
            precio=Decimal("1000"),
            es_predeterminada=True,
            activa=False,
        )

        respuesta = self.client.get(reverse("catalogo"))
        self.assertContains(respuesta, "Pie de prueba")
        self.assertContains(respuesta, "Pies de prueba")
        self.assertNotContains(respuesta, "Categoría inactiva")
        self.assertNotContains(respuesta, "Producto de categoría inactiva")
        self.assertNotContains(respuesta, "Producto inactivo")
        self.assertNotContains(respuesta, "Producto sin variante vendible")

    def test_el_buscador_muestra_todos_y_el_texto_del_encabezado(self):
        self._publicado()
        respuesta = self.client.get(reverse("catalogo"))
        self.assertContains(respuesta, "¿Qué dulce estás buscando?")
        self.assertContains(respuesta, "Buscar productos")
        self.assertContains(respuesta, "Limpiar búsqueda")
        self.assertContains(respuesta, "Todos")
        self.assertContains(respuesta, "Todas las categorías")
        self.assertContains(respuesta, "Categorías")
        self.assertContains(
            respuesta,
            "Descubre nuestros dulces artesanales, preparados con cariño para cada ocasión.",
        )
        self.assertNotContains(respuesta, "El precio corresponde a la variante elegida.")
        self.assertNotContains(respuesta, 'role="tab"')

    def test_oculta_variantes_inactivas_y_toma_el_precio_de_la_predeterminada_activa(self):
        producto = self._publicado(nombre_variante="Limón", precio=Decimal("4500"))
        crema = producto.variantes.get()
        crema.orden = 2
        crema.save(update_fields=["orden"])
        agregar_variante(producto=producto, nombre="Manzana", precio=Decimal("1800"), orden=0)
        retirada = agregar_variante(producto=producto, nombre="Retirada", precio=Decimal("9999"), orden=1)
        desactivar_variante(retirada)

        respuesta = self.client.get(reverse("catalogo"))
        self.assertContains(respuesta, "$4.500")
        self.assertContains(respuesta, 'data-precio="4500" checked')
        self.assertContains(respuesta, 'data-precio="1800"')
        self.assertNotContains(respuesta, 'data-precio="1800" checked')
        self.assertNotContains(respuesta, "Retirada")
        self.assertNotContains(respuesta, "9999")
        self.assertNotContains(respuesta, 'name="precio"')
        self.assertContains(respuesta, "<fieldset")
        html = respuesta.content.decode()
        self.assertIn('id="selector-%s"' % producto.pk, html)
        self.assertIn('name="variante"', html)
        self.assertEqual(formato_clp(producto.variantes.get(es_predeterminada=True).precio), "$4.500")

    def test_si_la_predeterminada_esta_inactiva_muestra_la_variante_activa(self):
        producto = Producto.objects.create(
            categoria=self.categoria,
            nombre="Precio honesto",
            slug="precio-honesto",
            activo=True,
        )
        VarianteProducto.objects.create(
            producto=producto,
            nombre="Retirada",
            precio=Decimal("9999"),
            es_predeterminada=True,
            activa=False,
        )
        VarianteProducto.objects.create(
            producto=producto,
            nombre="Disponible",
            precio=Decimal("1500"),
            es_predeterminada=False,
            activa=True,
            orden=1,
        )

        respuesta = self.client.get(reverse("catalogo"))
        self.assertContains(respuesta, "Precio honesto")
        self.assertContains(respuesta, "Disponible")
        self.assertContains(respuesta, "$1.500")
        self.assertNotContains(respuesta, "Retirada")
        self.assertNotContains(respuesta, "$9.999")
        self.assertNotContains(respuesta, "<fieldset")

    def test_producto_simple_no_muestra_selector(self):
        self._publicado()
        respuesta = self.client.get(reverse("catalogo"))
        self.assertContains(respuesta, "$4.500")
        self.assertNotContains(respuesta, "<fieldset")
        self.assertContains(respuesta, "Descripción visible de prueba")

    def test_consulta_publica_usa_pocas_consultas_y_ordena(self):
        otra = Categoria.objects.create(nombre="Antes", slug="antes", orden=0)
        self._publicado(nombre="Segundo", slug="segundo")
        crear_producto_con_variante_inicial(
            categoria=otra,
            nombre="Primero",
            slug="primero",
            precio=Decimal("1000"),
        )
        with CaptureQueriesContext(connection) as consultas:
            resultado = catalogo_publico()
        self.assertLessEqual(len(consultas), 2)
        self.assertEqual(
            [grupo["nombre"] for grupo in resultado["grupos"]],
            ["Antes", "Pies de prueba"],
        )
        self.assertEqual(resultado["grupos"][1]["productos"][0]["nombre"], "Segundo")

    def test_portada_conserva_sus_enlaces_y_no_mezcla_la_muestra(self):
        inicio = self.client.get(reverse("inicio"))
        self.assertEqual(inicio.status_code, 200)
        self.assertContains(inicio, "Un dulce momento, hecho")
        self.assertContains(inicio, "piedelimoninicio.png")
        self.assertContains(inicio, "alfajorinicio.png")
        self.assertContains(inicio, "rollosinicio.png")
        self.assertContains(inicio, f'href="{reverse("catalogo")}"')
        self.assertContains(inicio, "Explorar catálogo")
        self.assertContains(inicio, "Cotizar mi pedido")
        self.assertContains(inicio, f'href="{reverse("cotizaciones")}"')
        self.assertNotContains(inicio, "La cotización todavía no está disponible")
        self.assertNotContains(inicio, "El catálogo y la cotización todavía no están disponibles.")
        catalogo = self.client.get(reverse("catalogo"))
        self.assertNotContains(catalogo, "Alfajor de muestra")
        self.assertContains(catalogo, 'aria-current="page"')

    def _directorio_estatico(self, nombre="pieprueba.jpg", ancho=1280, alto=853):
        directorio = tempfile.TemporaryDirectory()
        self.addCleanup(directorio.cleanup)
        destino = Path(directorio.name) / "imagenes" / "catalogo-web" / nombre
        destino.parent.mkdir(parents=True)
        destino.write_bytes(
            b"\xff\xd8\xff\xc0\x00\x0b\x08"
            + alto.to_bytes(2, "big")
            + ancho.to_bytes(2, "big")
            + b"\x01\x01\x11\x00\xff\xd9"
        )
        return directorio.name

    def test_producto_con_fotografia_valida_y_producto_sin_fotografia(self):
        raiz = self._directorio_estatico()
        ruta = "imagenes/catalogo-web/pieprueba.jpg"
        with override_settings(STATICFILES_DIRS=[raiz]):
            self._publicado(referencia_imagen=ruta, nombre="Pie con foto", slug="pie-con-foto")
            self._publicado(nombre="Pie sin foto", slug="pie-sin-foto")
            respuesta = self.client.get(reverse("catalogo"))
        html = respuesta.content.decode()
        self.assertContains(respuesta, f'/static/{ruta}')
        self.assertContains(respuesta, 'alt="Fotografía de Pie con foto"')
        self.assertContains(respuesta, 'width="1280"')
        self.assertContains(respuesta, 'height="853"')
        self.assertContains(respuesta, 'loading="eager"')
        self.assertIn('alt="Fotografía de Pie con foto"', html)
        self.assertNotIn("Fotografía pendiente de Pie con foto", html)
        self.assertContains(respuesta, "Fotografía pendiente de Pie sin foto")
        self.assertContains(respuesta, "Pie sin foto")

    def test_rutas_inseguras_o_inexistentes_no_se_publican(self):
        peligrosas = [
            "https://evil.example/foto.jpg",
            "http://127.0.0.1:8001/static/secreto.jpg",
            r"C:\Users\ejemplo\foto.jpg",
            "imagenes/catalogo-web/../../secreto.jpg",
            "imagenes/catalogo-web/noexiste.jpg",
        ]
        for indice, ruta in enumerate(peligrosas):
            with self.subTest(ruta=ruta):
                self._publicado(
                    nombre=f"Producto riesgoso {indice}",
                    slug=f"producto-riesgoso-{indice}",
                    referencia_imagen=ruta,
                )
                respuesta = self.client.get(reverse("catalogo"))
                self.assertContains(respuesta, f"Fotografía pendiente de Producto riesgoso {indice}")
                self.assertNotContains(respuesta, "evil.example")
                self.assertNotContains(respuesta, "127.0.0.1")
                self.assertNotContains(respuesta, "secreto")
                self.assertNotContains(respuesta, "noexiste.jpg")

    def test_la_fotografia_conserva_selector_precios_y_producto_inactivo(self):
        raiz = self._directorio_estatico(ancho=1170, alto=1280)
        ruta = "imagenes/catalogo-web/pieprueba.jpg"
        with override_settings(STATICFILES_DIRS=[raiz]):
            producto = self._publicado(
                referencia_imagen=ruta,
                nombre="Rollo de prueba",
                slug="rollo-de-prueba",
                nombre_variante="Unidad",
                precio=Decimal("4500"),
            )
            agregar_variante(producto=producto, nombre="Caja", precio=Decimal("1800"), orden=1)
            crear_producto_con_variante_inicial(
                categoria=self.categoria,
                nombre="Rollo inactivo",
                slug="rollo-inactivo",
                precio=Decimal("1000"),
                referencia_imagen=ruta,
                activo=False,
            )
            respuesta = self.client.get(reverse("catalogo"))
        self.assertContains(respuesta, 'width="1170"')
        self.assertContains(respuesta, 'height="1280"')
        self.assertContains(respuesta, "$4.500")
        self.assertContains(respuesta, 'data-precio="4500" checked')
        self.assertContains(respuesta, 'data-precio="1800"')
        self.assertContains(respuesta, "<fieldset")
        self.assertContains(respuesta, "Caja")
        self.assertNotContains(respuesta, "Rollo inactivo")
        self.assertNotContains(respuesta, 'name="precio"')

    def test_precio_pendiente_confirmado_foto_e_inactivo(self):
        raiz = self._directorio_estatico()
        ruta = "imagenes/catalogo-web/pieprueba.jpg"
        with override_settings(STATICFILES_DIRS=[raiz]):
            producto = self._publicado(
                nombre="Presentación mixta",
                slug="presentacion-mixta",
                nombre_variante="Confirmada",
                precio=None,
                referencia_imagen=ruta,
            )
            agregar_variante(
                producto=producto,
                nombre="Con precio",
                precio=Decimal("1800"),
                orden=1,
            )
            crear_producto_con_variante_inicial(
                categoria=self.categoria,
                nombre="Oculto por inactivo",
                slug="oculto-por-inactivo",
                precio=None,
                activo=False,
                referencia_imagen=ruta,
            )
            cero = crear_producto_con_variante_inicial(
                categoria=self.categoria,
                nombre="Precio en cero",
                slug="precio-en-cero",
                precio=0,
            )
            respuesta = self.client.get(reverse("catalogo"))
        html = respuesta.content.decode()
        self.assertContains(respuesta, "Consultar precio")
        self.assertContains(respuesta, 'data-precio-pendiente="1" checked')
        self.assertContains(respuesta, 'data-precio="1800"')
        self.assertNotContains(respuesta, 'data-precio="1800" checked')
        self.assertContains(respuesta, f'/static/{ruta}')
        self.assertContains(respuesta, 'alt="Fotografía de Presentación mixta"')
        self.assertContains(respuesta, "$0")
        self.assertNotContains(respuesta, "Oculto por inactivo")
        self.assertNotIn('data-precio=""', html)
        self.assertNotIn("data-precio=\"None\"", html)
        self.assertEqual(cero.variantes.get().precio, Decimal("0"))

