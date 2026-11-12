"""Carga explícita de definiciones referenciales. Nunca abastece inventario."""
import hashlib
import json
import unicodedata
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection, transaction

from apps.catalogo.models import VarianteProducto
from apps.catalogo.rollitos import SLUG as SLUG_ROLLITOS
from .models import Insumo, Receta, RecetaIngrediente, PRECISA
from .servicios import cantidad_exacta


def clave_nombre(nombre):
    return " ".join("".join(c for c in unicodedata.normalize("NFKD", nombre) if not unicodedata.combining(c)).casefold().split())


def verificar_local():
    if not settings.DEBUG or getattr(settings, "EN_VERCEL", False) or connection.vendor != "sqlite":
        raise ValidationError("Este cargador solo admite SQLite local con DEBUG activo, fuera de Vercel.")


def _campos(objeto, campos, contexto):
    if not isinstance(objeto, dict) or set(objeto) != set(campos):
        raise ValidationError(f"{contexto}: campos requeridos: {', '.join(campos)}. No se admiten campos adicionales.")


def _cantidad(valor):
    if not isinstance(valor, str):
        raise ValidationError("Cantidades y rendimientos deben ser textos decimales exactos, sin valores provisionales.")
    return cantidad_exacta(valor, minimo=PRECISA)


def _nombre_demo(nombre):
    if not isinstance(nombre, str) or not nombre.strip() or not nombre.isprintable():
        raise ValidationError("El ingrediente necesita un nombre válido.")
    nombre = " ".join(nombre.split())
    if nombre.casefold().startswith("demo · "):
        nombre = nombre[7:].strip()
    if not nombre or len(nombre) > 113:
        raise ValidationError("Nombre de ingrediente vacío o demasiado largo.")
    # No deducir rendimientos de fruta/huevo ni descontar materia prima y derivado.
    if clave_nombre(nombre) in {"jugo de limon", "ralladura de limon", "yema", "yemas", "clara", "claras"}:
        raise ValidationError("Jugo/ralladura/yemas/claras requieren resolver primero su equivalencia con Limón o Huevos; no se crean automáticamente.")
    return "DEMO · " + nombre


def preparar_plan(datos):
    verificar_local()
    _campos(datos, ("version", "recetas"), "Recetario")
    if type(datos["version"]) is not int or datos["version"] != 1 or not isinstance(datos["recetas"], list):
        raise ValidationError("Se requiere version 1 y una lista de recetas.")
    variantes = {v.pk: v for v in VarianteProducto.objects.filter(activa=True, producto__activo=True,
        producto__categoria__activa=True).exclude(producto__slug=SLUG_ROLLITOS).select_related("producto")}
    if len(variantes) != 34:
        raise ValidationError("El catálogo no contiene exactamente las 34 variantes no compuestas esperadas. Revisa el alcance antes de continuar.")
    for slug in ("torta-de-bizcocho", "torta-de-galleta"):
        nombres = {v.nombre for v in variantes.values() if v.producto.slug == slug}
        if nombres != {f"{personas} personas" for personas in (10, 15, 20, 25, 30)}:
            raise ValidationError("Las tortas deben conservar sus cinco presentaciones: 10, 15, 20, 25 y 30 personas.")
    existentes = {}
    for insumo in Insumo.objects.all():
        if insumo.nombre.strip().casefold().startswith("demo · "):
            clave = clave_nombre(insumo.nombre)
            if clave in existentes:
                raise ValidationError("Hay nombres DEMO equivalentes duplicados. Deben resolverse antes de cargar.")
            existentes[clave] = insumo
    for nombre, unidad in {"Azúcar":"g", "Chocolate":"g", "Levadura":"g", "Manjar":"g", "Crema":"ml",
                          "Leche":"ml", "Harina":"g", "Mantequilla":"g", "Huevos":"unidad", "Limón":"unidad"}.items():
        insumo = existentes.get(clave_nombre("DEMO · " + nombre))
        if insumo is None or insumo.unidad != unidad or not insumo.activo:
            raise ValidationError(f"Revisar el insumo existente DEMO · {nombre}: debe estar activo y utilizar {unidad}. No se sustituye ni se duplica.")
    insumos, recetas, vistos, tortas = {}, [], set(), {}
    for entrada in datos["recetas"]:
        _campos(entrada, ("variante_id", "producto_slug", "presentacion", "unidad_rendimiento", "unidades_fisicas_por_presentacion", "rendimiento", "ingredientes"), "Receta")
        identificador = entrada["variante_id"]
        if type(identificador) is not int or identificador not in variantes or identificador in vistos:
            raise ValidationError("Variante duplicada, ajena al alcance o Rollitos de sabores incluido.")
        vistos.add(identificador)
        variante = variantes[identificador]
        if entrada["producto_slug"] != variante.producto.slug or entrada["presentacion"] != variante.nombre:
            raise ValidationError(f"La identificación de producto/presentación no coincide con la variante {identificador}.")
        fisicas = 4 if variante.nombre == "Caja de 4" else 1
        if entrada["unidad_rendimiento"] != "presentacion_comercial" or type(entrada["unidades_fisicas_por_presentacion"]) is not int or entrada["unidades_fisicas_por_presentacion"] != fisicas:
            raise ValidationError("El rendimiento debe expresarse en presentaciones comerciales: una Caja de 4 contiene cuatro unidades físicas.")
        rendimiento = _cantidad(entrada["rendimiento"])
        if not isinstance(entrada["ingredientes"], list) or not entrada["ingredientes"]:
            raise ValidationError("Cada receta debe tener ingredientes y cantidades exactas.")
        ingredientes, claves = [], set()
        for ingrediente in entrada["ingredientes"]:
            _campos(ingrediente, ("nombre", "unidad", "cantidad"), "Ingrediente")
            nombre = _nombre_demo(ingrediente["nombre"])
            clave = clave_nombre(nombre)
            if clave in claves:
                raise ValidationError("Un ingrediente equivalente aparece dos veces en la misma receta.")
            claves.add(clave)
            unidad, cantidad = ingrediente["unidad"], _cantidad(ingrediente["cantidad"])
            if unidad not in Insumo.Unidad.values:
                raise ValidationError("Unidad no admitida. No se convierten automáticamente unidades de masa, volumen o piezas.")
            if cantidad / rendimiento != (cantidad / rendimiento).quantize(PRECISA):
                raise ValidationError("El consumo por presentación supera la precisión de tres decimales. Revisa cantidades y rendimiento sin redondear automáticamente.")
            existente = existentes.get(clave)
            if existente and (existente.unidad != unidad or not existente.activo):
                raise ValidationError(f"Unidad incompatible o insumo inactivo: {existente.nombre}.")
            definicion = {"nombre": existente.nombre if existente else nombre, "unidad": unidad,
                          "id_existente": existente.pk if existente else None}
            if clave in insumos and insumos[clave] != definicion:
                raise ValidationError("El mismo ingrediente utiliza definiciones o unidades diferentes.")
            insumos[clave] = definicion
            ingredientes.append({"insumo": clave, "cantidad": str(cantidad)})
        ingredientes.sort(key=lambda i: i["insumo"])
        alcance = f"ejemplo:v{identificador}"
        receta = Receta.objects.filter(alcance=alcance).prefetch_related("ingredientes__insumo").first()
        if receta:
            original = sorted((clave_nombre(i.insumo.nombre), i.cantidad) for i in receta.ingredientes.all())
            deseado = sorted((i["insumo"], Decimal(i["cantidad"])) for i in ingredientes)
            if receta.producto_id != variante.producto_id or receta.variante_id != identificador or receta.rendimiento != rendimiento or original != deseado:
                raise ValidationError(f"La receta existente {alcance} es distinta. No se sobrescribe: requiere revisión separada.")
        recetas.append({"variante_id": identificador, "producto_id": variante.producto_id,
            "producto": variante.producto.nombre, "presentacion": variante.nombre, "alcance": alcance,
            "rendimiento": str(rendimiento), "ingredientes": ingredientes, "ya_existe": receta is not None})
        if variante.producto.slug in ("torta-de-bizcocho", "torta-de-galleta"):
            firma = tuple((i["insumo"], str((Decimal(i["cantidad"]) / rendimiento).normalize())) for i in ingredientes)
            grupo = tortas.setdefault(variante.producto_id, set())
            if firma in grupo:
                raise ValidationError("Dos tamaños de la misma torta tienen cantidades idénticas por presentación. Deben diferenciarse según el recetario.")
            grupo.add(firma)
    if vistos != set(variantes):
        raise ValidationError("El recetario debe incluir una receta para cada una de las 34 variantes no compuestas, sin omisiones.")
    plan = {"insumos": dict(sorted(insumos.items())), "recetas": sorted(recetas, key=lambda r: r["variante_id"])}
    plan["revision"] = hashlib.sha256(json.dumps(plan, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return plan


@transaction.atomic
def guardar_recetario(datos, revision):
    # Revalidar dentro de la transacción; no aceptar un archivo/plan cambiado.
    plan = preparar_plan(datos)
    if plan["revision"] != revision:
        raise ValidationError("La revisión no coincide con el archivo o el estado actual. Ejecuta primero una nueva vista previa.")
    registros = {}
    for clave, definicion in plan["insumos"].items():
        if definicion["id_existente"]:
            registros[clave] = Insumo.objects.get(pk=definicion["id_existente"])
        else:
            insumo = Insumo(nombre=definicion["nombre"], unidad=definicion["unidad"])
            insumo.full_clean(); insumo.save()
            registros[clave] = insumo
    for fila in plan["recetas"]:
        if fila["ya_existe"]:
            continue
        receta = Receta(producto_id=fila["producto_id"], variante_id=fila["variante_id"],
                        rendimiento=Decimal(fila["rendimiento"]), alcance=fila["alcance"])
        receta.full_clean(); receta.save()
        for ingrediente in fila["ingredientes"]:
            registro = RecetaIngrediente(receta=receta, insumo=registros[ingrediente["insumo"]], cantidad=Decimal(ingrediente["cantidad"]))
            registro.full_clean(); registro.save()
    return plan
