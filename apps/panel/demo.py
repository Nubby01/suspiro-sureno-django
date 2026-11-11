"""Datos de demostración aislados.

Las cantidades son ejemplos de prueba. No son la receta ni las existencias
del taller, y la receta marcada como ejemplo no se aplica a un pedido real.
"""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.catalogo.models import Producto
from apps.cotizaciones.models import Cotizacion, LineaCotizacion
from apps.cotizaciones.servicios import confirmar
from apps.cuentas.models import Usuario
from apps.inventario.models import Insumo, Receta, RecetaIngrediente
from apps.pedidos.models import Pedido
from apps.pedidos.servicios import cambiar_estado, convertir

MARCA = "DEMO · "
SLUG_PIE = "pie-de-limon"

INSUMOS = (
    ("DEMO · Harina", Insumo.Unidad.GRAMO, Decimal("300")),
    ("DEMO · Azúcar", Insumo.Unidad.GRAMO, Decimal("1")),
    ("DEMO · Huevos", Insumo.Unidad.UNIDAD, Decimal("6")),
    ("DEMO · Mantequilla", Insumo.Unidad.GRAMO, Decimal("150")),
    ("DEMO · Leche", Insumo.Unidad.MILILITRO, Decimal("1")),
    ("DEMO · Chocolate", Insumo.Unidad.GRAMO, Decimal("1")),
    ("DEMO · Manjar", Insumo.Unidad.GRAMO, Decimal("1")),
    ("DEMO · Crema", Insumo.Unidad.MILILITRO, Decimal("1")),
    ("DEMO · Limón", Insumo.Unidad.UNIDAD, Decimal("3")),
    ("DEMO · Levadura", Insumo.Unidad.GRAMO, Decimal("1")),
)

RECETA_EJEMPLO = (
    ("DEMO · Harina", Decimal("100")),
    ("DEMO · Mantequilla", Decimal("50")),
    ("DEMO · Huevos", Decimal("2")),
    ("DEMO · Limón", Decimal("1")),
)

PEDIDOS = (
    ("recibido", ()),
    ("preparacion", (Pedido.Estado.EN_PREPARACION,)),
    ("listo", (Pedido.Estado.EN_PREPARACION, Pedido.Estado.LISTO)),
    ("entregado", (Pedido.Estado.EN_PREPARACION, Pedido.Estado.LISTO, Pedido.Estado.ENTREGADO)),
    ("cancelado", (Pedido.Estado.CANCELADO,)),
)


def observacion(clave):
    return (
        f"{MARCA}Pedido de demostración ({clave}). "
        "Las cantidades son un ejemplo de prueba y no son la receta del taller."
    )


def _clienta():
    clienta = Usuario.objects.filter(username="demo-clienta", rol=Usuario.Rol.CLIENTE).first()
    if clienta is None:
        raise ValidationError(
            "No existe demo-clienta. Créala con el comando de cuentas de demostración "
            "antes de cargar estos ejemplos."
        )
    return clienta


def _responsable():
    return Usuario.objects.filter(username="demo-administradora").first()


def _insumos():
    creados = []
    for nombre, unidad, existencia in INSUMOS:
        insumo, nuevo = Insumo.objects.get_or_create(
            nombre=nombre,
            defaults={
                "unidad": unidad,
                "existencia": existencia,
                "stock_minimo": Decimal("0"),
                "activo": True,
            },
        )
        creados.append((insumo, nuevo))
    return creados


def _receta_ejemplo(producto, insumos):
    alcance = f"ejemplo:p{producto.pk}"
    receta = Receta.objects.filter(alcance=alcance).first()
    if receta is None:
        receta = Receta(producto=producto, variante=None, rendimiento=Decimal("1"), alcance=alcance)
        receta.save()
    por_nombre = {insumo.nombre: insumo for insumo, _nuevo in insumos}
    for nombre, cantidad in RECETA_EJEMPLO:
        RecetaIngrediente.objects.get_or_create(
            receta=receta,
            insumo=por_nombre[nombre],
            defaults={"cantidad": cantidad},
        )
    return receta


def _pedido(clienta, producto, variante, responsable, clave, avances):
    texto = observacion(clave)
    if Cotizacion.objects.filter(observaciones=texto).exists():
        return False
    cotizacion = Cotizacion.objects.create(
        cliente=clienta,
        nombre=clienta.get_full_name() or "Clienta de demostración",
        correo=clienta.email or "demo-clienta@example.com",
        telefono=clienta.telefono or "+56900000000",
        observaciones=texto,
    )
    LineaCotizacion.objects.create(
        cotizacion=cotizacion,
        variante=variante,
        nombre_producto=producto.nombre,
        nombre_variante=variante.nombre,
        detalle="Ejemplo de demostración",
        cantidad=1,
        precio_acordado=variante.precio,
    )
    confirmar(cotizacion=cotizacion)
    pedido = convertir(cotizacion=cotizacion, usuario=responsable)
    for estado in avances:
        nota = "Ejemplo de demostración."
        if estado == Pedido.Estado.CANCELADO:
            nota = "Ejemplo de demostración cancelado antes de prepararlo."
        cambiar_estado(pedido=pedido, estado=estado, usuario=responsable, nota=nota)
    return True


@transaction.atomic
def cargar_demo_negocio():
    if not settings.DEBUG:
        raise ValidationError("Bloqueado fuera de desarrollo. No se escribieron ejemplos.")
    clienta = _clienta()
    responsable = _responsable() or clienta
    insumos = _insumos()
    producto = Producto.objects.filter(slug=SLUG_PIE, activo=True).first()
    variante = None
    if producto is not None:
        variante = (
            producto.variantes.filter(activa=True, precio__isnull=False)
            .order_by("-es_predeterminada", "orden", "id")
            .first()
        )
    pedidos_nuevos = 0
    if variante is not None:
        _receta_ejemplo(producto, insumos)
        for clave, avances in PEDIDOS:
            if _pedido(clienta, producto, variante, responsable, clave, avances):
                pedidos_nuevos += 1
    return {
        "insumos": len(insumos),
        "pedidos_nuevos": pedidos_nuevos,
        "con_producto": variante is not None,
    }
