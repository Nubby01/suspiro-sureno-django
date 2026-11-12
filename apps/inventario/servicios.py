"""Reglas de inventario. No modifican precios ni crean recetas por su cuenta.

En SQLite, select_for_update no bloquea filas: Django 5.1 deja
has_select_for_update en False y omite FOR UPDATE. Lo comprobado es la
clave única del movimiento, la relación única de ConsumoPedido y
transaction.atomic. En PostgreSQL, SELECT FOR UPDATE bloquea la fila
además de esas restricciones. No se afirma el resultado de dos escrituras
simultáneas en SQLite: una puede recibir «database is locked» y, en ese
caso, el movimiento se rechaza sin aplicarse.
"""

import re
import hashlib
import json
import unicodedata
from django.utils import timezone
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import IntegrityError, OperationalError, transaction
from django.db.models import F

from apps.catalogo.rollitos import SLUG as SLUG_ROLLITOS
from apps.catalogo.brownie import SLUG as SLUG_BROWNIE
from apps.catalogo.berlines import SLUG as SLUG_BERLINES

from .models import Abastecimiento, SalidaLote, PRECISA, ConsumoPedido, Insumo, MovimientoInventario, Receta, RecetaIngrediente

MENSAJE_CANTIDAD = "Indica una cantidad con hasta 3 decimales."
MENSAJE_EXISTENCIA = "La existencia no puede quedar negativa."
MENSAJE_UNIDAD = "La unidad debe ser la misma del insumo."
MENSAJE_DUPLICADO = "Ese movimiento ya estaba registrado."
MENSAJE_INACTIVO = "Ese insumo no está activo."
MENSAJE_SIN_RECETA = (
    "Falta la receta de {nombre}. No se descuentan cantidades estimadas "
    "y el pedido sigue pendiente de preparación."
)
MENSAJE_ROLLITOS = (
    "Rollitos de sabores no tiene un consumo determinado. "
    "El pedido sigue pendiente de resolución y no se descontaron ingredientes."
)
MENSAJE_COMPOSICION_PENDIENTE = (
    "{nombre} tiene rellenos seleccionables cuya composición necesita definirse "
    "antes de descontar ingredientes. No se inició la preparación ni se descontaron "
    "insumos del pedido."
)
MENSAJE_STOCK = "No hay existencia suficiente de {nombre}. No se modificó el inventario."
MENSAJE_YA_CONSUMIO = "Este pedido ya descontó inventario."
MENSAJE_PRECISION = "El consumo de {nombre} no coincide con la precisión de 3 decimales."
MENSAJE_CAJA = (
    "Rollitos de sabores no tiene una receta única. "
    "Configura cada sabor por separado."
)


def _referencia_compra(datos, insumo_id):
    datos = dict(datos or {})
    if not datos.get("es_compra"):
        if datos.get("referencia_compra") or datos.get("tipo_referencia"):
            raise ValidationError("Una referencia de compra requiere marcar Es una compra.")
        return datos
    if not datos.get("fecha_compra") or datos.get("precio_compra") is None or not str(datos.get("proveedor") or "").strip():
        raise ValidationError("La compra requiere fecha, importe y proveedor.")
    if datos["fecha_compra"] > timezone.localdate():
        raise ValidationError("La fecha de compra no puede ser posterior a hoy.")
    if datos.get("tipo_referencia") not in ("documento", "interna") or not str(datos.get("referencia_compra") or "").strip():
        raise ValidationError("Indica una referencia real de documento o una referencia interna de la compra.")
    if datos.get("caducidad") and datos["caducidad"] < datos["fecha_compra"]:
        raise ValidationError("La caducidad no puede ser anterior a la compra.")
    datos["proveedor"] = datos["proveedor"].strip()
    datos["referencia_compra"] = datos["referencia_compra"].strip()
    normalizar = lambda s: " ".join(unicodedata.normalize("NFKC", s).casefold().split())
    identidad = [normalizar(datos["proveedor"]), datos["tipo_referencia"], normalizar(datos["referencia_compra"]), insumo_id]
    datos["huella_compra"] = hashlib.sha256(json.dumps(identidad, ensure_ascii=False).encode()).hexdigest()
    if Abastecimiento.objects.filter(huella_compra=datos["huella_compra"]).exists():
        raise ValidationError("Ya se registró este insumo con la misma referencia y proveedor. No se ingresó stock otra vez.")
    return datos


def cantidad_exacta(valor, *, minimo=None, permitir_cero=False):
    texto = str(valor if valor is not None else "").strip().replace(",", ".")
    if not re.fullmatch(r"-?\d{1,9}(?:\.\d{1,3})?", texto):
        raise ValidationError(MENSAJE_CANTIDAD)
    try:
        numero = Decimal(texto)
    except InvalidOperation as exc:
        raise ValidationError(MENSAJE_CANTIDAD) from exc
    if not permitir_cero and numero == 0:
        raise ValidationError(MENSAJE_CANTIDAD)
    if minimo is not None and numero < minimo:
        raise ValidationError(MENSAJE_CANTIDAD)
    return numero


def guardar_insumo(*, insumo, nombre, unidad, stock_minimo, activo, stock_critico=None):
    nombre = (nombre or "").strip()
    if not nombre:
        raise ValidationError("Completa el nombre del insumo.")
    if unidad not in Insumo.Unidad.values:
        raise ValidationError("Elige una unidad de medida.")
    minimo = cantidad_exacta(stock_minimo, minimo=Decimal("0"), permitir_cero=True)
    repetido = Insumo.objects.filter(nombre__iexact=nombre)
    if insumo.pk:
        repetido = repetido.exclude(pk=insumo.pk)
    if repetido.exists():
        raise ValidationError("Ya existe un insumo con ese nombre.")
    if insumo.pk and insumo.unidad != unidad:
        if insumo.movimientos.exists() or insumo.ingredientes.exists():
            raise ValidationError(
                "No se puede cambiar la unidad porque ya hay movimientos o recetas."
            )
    insumo.nombre = nombre[:120]
    insumo.unidad = unidad
    insumo.stock_minimo = minimo
    insumo.stock_critico = None if stock_critico in (None, "") else cantidad_exacta(stock_critico, minimo=0, permitir_cero=True)
    insumo.activo = bool(activo)
    if not insumo.pk:
        insumo.existencia = Decimal("0")
    insumo.full_clean()
    insumo.save()
    return insumo


def _usuario(usuario):
    if getattr(usuario, "is_authenticated", False):
        return usuario
    return None


def validar_insumo_comercial(insumo):
    nombre = insumo.nombre.strip().casefold()
    if nombre.startswith(("demo · ", "ejemplo de prueba")):
        raise ValidationError("Una receta comercial no puede utilizar insumos DEMO. Usa una receta de ejemplo o un insumo comercial real.")


def _receta_segura(receta):
    if not receta.alcance.startswith("ejemplo:"):
        for ingrediente in receta.ingredientes.all():
            validar_insumo_comercial(ingrediente.insumo)
    return receta


@transaction.atomic
def registrar_movimiento(*, insumo, tipo, cantidad, motivo, usuario, clave, pedido=None, consumo=False, abastecimiento=None):
    clave = (clave or "").strip()
    if not clave or len(clave) > 64:
        raise ValidationError("No se pudo identificar el movimiento.")
    existente = MovimientoInventario.objects.filter(clave=clave).first()
    if existente is not None:
        return existente, False
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValidationError("Indica el motivo del movimiento.")
    if tipo not in (MovimientoInventario.Tipo.ENTRADA, MovimientoInventario.Tipo.AJUSTE, MovimientoInventario.Tipo.CONSUMO):
        raise ValidationError("Ese tipo de movimiento no está permitido.")
    if tipo == MovimientoInventario.Tipo.CONSUMO and not consumo:
        raise ValidationError("El consumo solo se registra al iniciar la preparación.")
    delta = cantidad_exacta(
        cantidad,
        permitir_cero=False,
        minimo=None if tipo == MovimientoInventario.Tipo.AJUSTE else Decimal("0"),
    )
    if tipo == MovimientoInventario.Tipo.ENTRADA and delta <= 0:
        raise ValidationError("La entrada debe ser mayor que cero.")
    if tipo == MovimientoInventario.Tipo.AJUSTE and delta == 0:
        raise ValidationError(MENSAJE_CANTIDAD)
    if tipo == MovimientoInventario.Tipo.CONSUMO:
        if delta <= 0:
            raise ValidationError(MENSAJE_CANTIDAD)
        delta = -delta
    try:
        with transaction.atomic():
            otra_vez = MovimientoInventario.objects.filter(clave=clave).first()
            if otra_vez is not None:
                return otra_vez, False
            bloqueado = Insumo.objects.select_for_update().get(pk=insumo.pk)
            if not bloqueado.activo:
                raise ValidationError(MENSAJE_INACTIVO)
            resultante = bloqueado.existencia + delta
            if resultante < 0:
                raise ValidationError(MENSAJE_EXISTENCIA)
            bloqueado.existencia = resultante
            bloqueado.save(update_fields=["existencia", "actualizado"])
            movimiento = MovimientoInventario(
                insumo=bloqueado,
                pedido=pedido,
                tipo=tipo,
                cantidad=delta,
                existencia_resultante=resultante,
                motivo=motivo[:500],
                usuario=_usuario(usuario),
                clave=clave,
            )
            movimiento.full_clean()
            movimiento.save()
            if tipo == MovimientoInventario.Tipo.ENTRADA:
                datos = _referencia_compra(abastecimiento, bloqueado.pk)
                permitidos = {"es_compra", "fecha_compra", "precio_compra", "proveedor", "caducidad", "lote", "observaciones", "tipo_referencia", "referencia_compra", "huella_compra"}
                registro = Abastecimiento(movimiento=movimiento, cantidad_inicial=delta, saldo=delta, unidad=bloqueado.unidad, **{k:v for k,v in datos.items() if k in permitidos})
                registro.full_clean()
                registro.save()
            elif delta < 0:
                # FEFO autorizado: fechas conocidas primero, luego sin fecha; orden de ingreso desempata.
                pendiente = -delta
                lotes = Abastecimiento.objects.select_for_update().filter(movimiento__insumo=bloqueado, saldo__gt=0).order_by(F("caducidad").asc(nulls_last=True), "movimiento__creada", "pk")
                for lote in lotes:
                    usado = min(pendiente, lote.saldo)
                    if usado <= 0:
                        break
                    lote.saldo -= usado
                    lote.save(update_fields=["saldo"])
                    SalidaLote.objects.create(abastecimiento=lote, movimiento=movimiento, cantidad=usado)
                    pendiente -= usado
                # El remanente corresponde a existencia anterior o ajustes positivos sin lote registrado.
            return movimiento, True
    except IntegrityError as exc:
        encontrado = MovimientoInventario.objects.filter(clave=clave).first()
        if encontrado is not None:
            return encontrado, False
        raise ValidationError(MENSAJE_DUPLICADO) from exc
    except OperationalError as exc:
        raise ValidationError("No se pudo registrar el movimiento. Intenta nuevamente.") from exc


def agregar_ingrediente(*, producto, variante, insumo, cantidad, rendimiento, unidad):
    validar_insumo_comercial(insumo)
    if variante is not None and variante.producto_id != producto.pk:
        raise ValidationError("La variante no pertenece a ese producto.")
    if producto.slug == SLUG_ROLLITOS:
        raise ValidationError(MENSAJE_CAJA)
    if unidad != insumo.unidad:
        raise ValidationError(MENSAJE_UNIDAD)
    cantidad = cantidad_exacta(cantidad, minimo=PRECISA)
    rendimiento = cantidad_exacta(rendimiento, minimo=PRECISA)
    with transaction.atomic():
        alcance = f"v{variante.pk}" if variante is not None else f"p{producto.pk}"
        receta = Receta.objects.select_for_update().filter(alcance=alcance).first()
        if receta is None:
            receta = Receta(producto=producto, variante=variante, rendimiento=rendimiento)
            receta.alcance = alcance
            receta.full_clean()
            receta.save()
        else:
            receta.rendimiento = rendimiento
            receta.full_clean()
            receta.save(update_fields=["rendimiento", "actualizada"])
        ingrediente = receta.ingredientes.filter(insumo=insumo).first()
        if ingrediente is None:
            ingrediente = RecetaIngrediente(receta=receta, insumo=insumo, cantidad=cantidad)
        else:
            ingrediente.cantidad = cantidad
        ingrediente.full_clean()
        ingrediente.save()
    return receta


@transaction.atomic
def quitar_ingrediente(*, ingrediente_id):
    ingrediente = (
        RecetaIngrediente.objects.select_for_update()
        .select_related("receta")
        .filter(pk=ingrediente_id)
        .first()
    )
    if ingrediente is None:
        raise ValidationError("No encontramos ese ingrediente.")
    receta = ingrediente.receta
    ingrediente.delete()
    if not receta.ingredientes.exists():
        receta.delete()


def _consumo_linea(linea, receta):
    requerimientos = {}
    ingredientes = list(receta.ingredientes.select_related("insumo"))
    if not ingredientes:
        raise ValidationError(MENSAJE_SIN_RECETA.format(nombre=linea.nombre_producto))
    for ingrediente in ingredientes:
        if not ingrediente.insumo.activo:
            raise ValidationError(f"{ingrediente.insumo.nombre} está inactivo. No se descontó inventario.")
        if ingrediente.insumo.unidad is None:
            raise ValidationError(MENSAJE_UNIDAD)
        consumo = (Decimal(linea.cantidad) * ingrediente.cantidad) / receta.rendimiento
        if consumo != consumo.quantize(PRECISA):
            raise ValidationError(MENSAJE_PRECISION.format(nombre=ingrediente.insumo.nombre))
        requerimientos[ingrediente.insumo_id] = requerimientos.get(ingrediente.insumo_id, Decimal("0")) + consumo
    return requerimientos


def pedido_es_demostracion(pedido):
    cotizacion = getattr(pedido, "cotizacion", None)
    return (getattr(cotizacion, "observaciones", "") or "").startswith("DEMO · ")


def _recetas_de_linea(linea):
    """Las recetas de ejemplo no alimentan un pedido real."""
    consulta = Receta.objects.all()
    if pedido_es_demostracion(linea.pedido):
        ejemplos = consulta.filter(alcance__startswith="ejemplo:")
        if ejemplos.filter(producto=linea.variante.producto).exists():
            return ejemplos
    return consulta.exclude(alcance__startswith="ejemplo:")


def _receta_de_linea(linea):
    producto = linea.variante.producto
    if producto.slug == SLUG_ROLLITOS:
        raise ValidationError(MENSAJE_ROLLITOS)
    # Bloqueo temporal por identidad del producto, igual que Rollitos: no depende
    # del ID de la base, de que exista receta o de si es comercial o DEMO.
    if producto.slug in (SLUG_BROWNIE, SLUG_BERLINES):
        raise ValidationError(MENSAJE_COMPOSICION_PENDIENTE.format(nombre=producto.nombre))
    consulta = _recetas_de_linea(linea)
    especifica = (
        consulta.filter(variante=linea.variante)
        .prefetch_related("ingredientes__insumo")
        .first()
    )
    if especifica is not None:
        return _receta_segura(especifica)
    general = (
        consulta.filter(producto=producto, variante__isnull=True)
        .prefetch_related("ingredientes__insumo")
        .first()
    )
    if general is None:
        raise ValidationError(MENSAJE_SIN_RECETA.format(nombre=linea.nombre_producto))
    return _receta_segura(general)


@transaction.atomic
def consumir_para_preparacion(*, pedido, usuario):
    """Descuenta una sola vez. Debe llamarse dentro de la transacción del pedido."""
    if ConsumoPedido.objects.filter(pedido=pedido).exists():
        raise ValidationError(MENSAJE_YA_CONSUMIO)
    lineas = list(pedido.lineas.select_related("variante__producto"))
    if not lineas:
        raise ValidationError("El pedido no tiene productos para preparar.")
    total = {}
    for linea in lineas:
        receta = _receta_de_linea(linea)
        for insumo_id, cantidad in _consumo_linea(linea, receta).items():
            total[insumo_id] = total.get(insumo_id, Decimal("0")) + cantidad
    insumos = {
        insumo.pk: insumo
        for insumo in Insumo.objects.select_for_update().filter(pk__in=sorted(total)).order_by("id")
    }
    if len(insumos) != len(total):
        raise ValidationError(MENSAJE_SIN_RECETA.format(nombre="un producto del pedido"))
    for insumo_id, necesario in total.items():
        insumo = insumos[insumo_id]
        if not insumo.activo:
            raise ValidationError(f"{insumo.nombre} está inactivo. No se descontó inventario.")
        if insumo.existencia < necesario:
            raise ValidationError(MENSAJE_STOCK.format(nombre=insumo.nombre))
    try:
        with transaction.atomic():
            ConsumoPedido.objects.create(pedido=pedido, usuario=_usuario(usuario))
    except IntegrityError as exc:
        raise ValidationError(MENSAJE_YA_CONSUMIO) from exc
    for insumo_id in sorted(total):
        registrar_movimiento(
            insumo=insumos[insumo_id],
            tipo=MovimientoInventario.Tipo.CONSUMO,
            cantidad=total[insumo_id],
            motivo=f"Preparación del pedido {pedido.codigo}.",
            usuario=usuario,
            clave=f"consumo-{pedido.pk}-{insumo_id}",
            pedido=pedido,
            consumo=True,
        )
