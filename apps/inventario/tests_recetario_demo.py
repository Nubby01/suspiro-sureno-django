"""Datos sintéticos de pruebas: no constituyen el recetario referencial del usuario."""
import copy
import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.forms.models import inlineformset_factory
from django.test import TestCase, override_settings

from apps.catalogo.models import Categoria, Producto, VarianteProducto
from apps.cotizaciones.models import Cotizacion
from apps.pedidos.models import Pedido, LineaPedido, VentaPedido
from .admin import IngredientesSegurosFormSet
from .models import Insumo, Receta, RecetaIngrediente, MovimientoInventario, Abastecimiento
from .recetario_demo import preparar_plan, guardar_recetario
from .servicios import agregar_ingrediente, consumir_para_preparacion


@override_settings(DEBUG=True, EN_VERCEL=False)
class RecetarioDemoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        categoria = Categoria.objects.create(nombre="Categoría QA", slug="categoria-qa")
        for nombre, unidad in {"Azúcar":"g","Chocolate":"g","Levadura":"g","Manjar":"g","Crema":"ml",
            "Leche":"ml","Harina":"g","Mantequilla":"g","Huevos":"unidad","Limón":"unidad"}.items():
            Insumo.objects.create(nombre="DEMO · "+nombre,unidad=unidad)
        cls.datos={"version":1,"recetas":[]}
        def agregar(producto, nombre, cantidad):
            variante=VarianteProducto.objects.create(producto=producto,nombre=nombre,precio=1000)
            cls.datos["recetas"].append({"variante_id":variante.pk,"producto_slug":producto.slug,
                "presentacion":nombre,"unidad_rendimiento":"presentacion_comercial",
                "unidades_fisicas_por_presentacion":4 if nombre=="Caja de 4" else 1,
                "rendimiento":"1","ingredientes":[{"nombre":"Harina","unidad":"g","cantidad":str(cantidad)},
                    {"nombre":"Maicena QA","unidad":"g","cantidad":"1"}]})
        for n in range(24):
            producto=Producto.objects.create(categoria=categoria,nombre=f"Producto sintético QA {n}",slug=f"producto-qa-{n}")
            agregar(producto,"Caja de 4" if n==0 else "",10+n)
        for slug in ("torta-de-bizcocho","torta-de-galleta"):
            producto=Producto.objects.create(categoria=categoria,nombre=slug,slug=slug)
            for personas in (10,15,20,25,30):agregar(producto,f"{personas} personas",personas)
        producto=Producto.objects.create(categoria=categoria,nombre="Rollitos QA",slug="rollitos-de-sabores")
        cls.rollitos=VarianteProducto.objects.create(producto=producto,nombre="Caja de 4",precio=1000)

    def test_revision_no_escribe_y_reutiliza_unidades_e_ids(self):
        antes=(Insumo.objects.count(),Receta.objects.count())
        plan=preparar_plan(self.datos)
        self.assertEqual(len(plan["recetas"]),34)
        self.assertEqual(plan["insumos"]["demo · harina"]["id_existente"],Insumo.objects.get(nombre="DEMO · Harina").pk)
        self.assertEqual((Insumo.objects.count(),Receta.objects.count()),antes)
        self.assertFalse(MovimientoInventario.objects.exists())

    def test_guardar_y_repetir_sin_stocks_compras_ventas_ni_duplicados(self):
        plan=preparar_plan(self.datos)
        guardar_recetario(self.datos,plan["revision"])
        plan=preparar_plan(self.datos)
        guardar_recetario(self.datos,plan["revision"])
        self.assertEqual(Receta.objects.count(),34)
        self.assertEqual(Insumo.objects.count(),11)
        self.assertFalse(Insumo.objects.exclude(existencia=0).exists())
        self.assertFalse(MovimientoInventario.objects.exists())
        self.assertFalse(Abastecimiento.objects.exists())
        self.assertFalse(VentaPedido.objects.exists())
        self.assertFalse(Receta.objects.filter(producto=self.rollitos.producto).exists())
        self.assertTrue(all(r.variante_id and r.alcance==f"ejemplo:v{r.variante_id}" for r in Receta.objects.all()))

    def test_faltantes_duplicados_rollitos_unidades_y_fracciones_invalidas(self):
        casos=[]
        datos=copy.deepcopy(self.datos);datos["recetas"].pop();casos.append(datos)
        datos=copy.deepcopy(self.datos);datos["recetas"][1]=datos["recetas"][0];casos.append(datos)
        datos=copy.deepcopy(self.datos);datos["recetas"][0]["variante_id"]=self.rollitos.pk;casos.append(datos)
        datos=copy.deepcopy(self.datos);datos["recetas"][0]["ingredientes"][0]["unidad"]="kg";casos.append(datos)
        datos=copy.deepcopy(self.datos);datos["recetas"][0]["rendimiento"]="3";casos.append(datos)
        datos=copy.deepcopy(self.datos);datos["recetas"][0]["unidades_fisicas_por_presentacion"]=1;casos.append(datos)
        datos=copy.deepcopy(self.datos);datos["recetas"][0]["ingredientes"].append({"nombre":"ralladura de limón","cantidad":"1","unidad":"g"});casos.append(datos)
        for datos in casos:
            with self.subTest(datos=datos["recetas"][0]):
                with self.assertRaises(ValidationError):preparar_plan(datos)
        self.assertFalse(Receta.objects.exists())

    def test_tortas_requieren_cantidades_por_presentacion_diferentes(self):
        datos=copy.deepcopy(self.datos)
        datos["recetas"][25]["ingredientes"]=copy.deepcopy(datos["recetas"][24]["ingredientes"])
        with self.assertRaisesMessage(ValidationError,"Dos tamaños"):
            preparar_plan(datos)

    def test_conflicto_no_sobrescribe_y_revision_obsoleta_no_guarda(self):
        plan=preparar_plan(self.datos)
        datos=copy.deepcopy(self.datos)
        datos["recetas"][0]["ingredientes"][0]["cantidad"]="99"
        with self.assertRaisesMessage(ValidationError,"revisión"):
            guardar_recetario(datos,plan["revision"])
        self.assertFalse(Receta.objects.exists())
        guardar_recetario(self.datos,plan["revision"])
        with self.assertRaisesMessage(ValidationError,"No se sobrescribe"):
            preparar_plan(datos)
        self.assertEqual(Receta.objects.first().ingredientes.get(insumo__nombre="DEMO · Harina").cantidad,10)

    def test_transaccion_revierte_todo_si_falla_una_receta(self):
        plan=preparar_plan(self.datos)
        with patch.object(RecetaIngrediente,"save",side_effect=ValidationError("Fallo QA")):
            with self.assertRaises(ValidationError):guardar_recetario(self.datos,plan["revision"])
        self.assertEqual(Insumo.objects.count(),10)
        self.assertFalse(Receta.objects.exists())

    def test_comando_previsualiza_y_exige_confirmacion_sin_respaldar(self):
        with tempfile.TemporaryDirectory() as carpeta:
            archivo=Path(carpeta)/"solo-pruebas.json"
            archivo.write_text(json.dumps(self.datos),encoding="utf-8")
            salida=io.StringIO()
            with patch("apps.inventario.management.commands.preparar_recetario_demo.respaldar_local") as respaldo:
                call_command("preparar_recetario_demo",str(archivo),stdout=salida)
                with self.assertRaises(CommandError):call_command("preparar_recetario_demo",str(archivo),guardar=True,stdout=io.StringIO())
                respaldo.assert_not_called()
            self.assertIn("Solo revisión",salida.getvalue())
        self.assertFalse(Receta.objects.exists())

    def test_produccion_se_bloquea_sin_consultar_tablas(self):
        with override_settings(DEBUG=False),self.assertNumQueries(0):
            with self.assertRaises(CommandError):call_command("preparar_recetario_demo","no-existe.json",stdout=io.StringIO())
        with override_settings(EN_VERCEL=True),self.assertNumQueries(0):
            with self.assertRaises(CommandError):call_command("preparar_recetario_demo","no-existe.json",stdout=io.StringIO())
        with patch("apps.inventario.recetario_demo.connection",SimpleNamespace(vendor="postgresql")),self.assertNumQueries(0):
            with self.assertRaises(CommandError):call_command("preparar_recetario_demo","no-existe.json",stdout=io.StringIO())

    def test_no_modifica_receta_ni_saldos_existentes(self):
        variante=VarianteProducto.objects.exclude(pk=self.rollitos.pk).first()
        insumo=Insumo.objects.get(nombre="DEMO · Harina")
        insumo.existencia=7;insumo.stock_minimo=3;insumo.stock_critico=1;insumo.save()
        receta=Receta.objects.create(producto=variante.producto,rendimiento=2,alcance=f"ejemplo:p{variante.producto_id}")
        ingrediente=RecetaIngrediente.objects.create(receta=receta,insumo=insumo,cantidad=5)
        antes=receta.actualizada
        plan=preparar_plan(self.datos)
        guardar_recetario(self.datos,plan["revision"])
        insumo.refresh_from_db();receta.refresh_from_db();ingrediente.refresh_from_db()
        self.assertEqual((insumo.existencia,insumo.stock_minimo,insumo.stock_critico),(7,3,1))
        self.assertEqual((receta.rendimiento,receta.actualizada,ingrediente.cantidad),(2,antes,5))

    def test_no_mezclar_demo_en_servicio_admin_o_receta_comercial_preexistente(self):
        variante=VarianteProducto.objects.exclude(pk=self.rollitos.pk).first()
        insumo=Insumo.objects.get(nombre="DEMO · Harina")
        with self.assertRaises(ValidationError):
            agregar_ingrediente(producto=variante.producto,variante=variante,insumo=insumo,cantidad="1",rendimiento="1",unidad="g")
        receta=Receta.objects.create(producto=variante.producto,variante=variante,rendimiento=1)
        Clase=inlineformset_factory(Receta,RecetaIngrediente,formset=IngredientesSegurosFormSet,fields=("insumo","cantidad"),extra=1)
        formulario=Clase({"ingredientes-TOTAL_FORMS":"1","ingredientes-INITIAL_FORMS":"0","ingredientes-0-insumo":str(insumo.pk),"ingredientes-0-cantidad":"1"},instance=receta,prefix="ingredientes")
        self.assertFalse(formulario.is_valid())
        self.assertIn("DEMO",str(formulario.non_form_errors()))
        RecetaIngrediente.objects.create(receta=receta,insumo=insumo,cantidad=1)
        cotizacion=Cotizacion.objects.create(nombre="QA",correo="qa@example.com",telefono="+56900000000")
        pedido=Pedido.objects.create(cotizacion=cotizacion,nombre="QA",correo="qa@example.com",telefono="+56900000000",total=1000)
        LineaPedido.objects.create(pedido=pedido,variante=variante,nombre_producto=variante.producto.nombre,cantidad=1,precio_acordado=1000)
        with self.assertRaisesMessage(ValidationError,"DEMO"):
            consumir_para_preparacion(pedido=pedido,usuario=None)
        self.assertFalse(MovimientoInventario.objects.exists())
