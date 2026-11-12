"""Insumos, recetas y movimientos.

Reglas provisionales, pendientes de validación comercial:

- Una cotización no descuenta existencias.
- Confirmar una cotización no descuenta existencias.
- Crear un pedido no descuenta existencias.
- El consumo se registra una sola vez, al pasar el pedido a «En preparación»,
  y solo si cada línea tiene una receta completa y hay existencia suficiente.
- Si falta stock, no se descuenta y la existencia no queda negativa.
- Si falta una receta, no se estiman ingredientes.
- Rollitos de sabores no usa una receta única: si el consumo no se puede
  calcular con las selecciones guardadas, el pedido sigue pendiente.
- Cancelar después de iniciar la preparación no devuelve ingredientes.
  La devolución queda para un ajuste manual, con motivo y responsable.
"""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower

from apps.catalogo.rollitos import SLUG as SLUG_ROLLITOS


PRECISA = Decimal("0.001")


class Insumo(models.Model):
    class Unidad(models.TextChoices):
        GRAMO = "g", "Gramos"
        KILOGRAMO = "kg", "Kilogramos"
        MILILITRO = "ml", "Mililitros"
        LITRO = "l", "Litros"
        UNIDAD = "unidad", "Unidades"

    nombre = models.CharField("nombre", max_length=120)
    unidad = models.CharField("unidad", max_length=20, choices=Unidad.choices)
    existencia = models.DecimalField(
        "existencia",
        max_digits=12,
        decimal_places=3,
        default=Decimal("0"),
    )
    stock_minimo = models.DecimalField(
        "stock mínimo",
        max_digits=12,
        decimal_places=3,
        default=Decimal("0"),
    )
    stock_critico = models.DecimalField("stock crítico", max_digits=12, decimal_places=3, null=True, blank=True, help_text="Umbral absoluto opcional, entre 0 y el stock mínimo. Vacío desactiva el nivel crítico.")
    activo = models.BooleanField("activo", default=True)
    actualizado = models.DateTimeField("actualizado", auto_now=True)

    class Meta:
        verbose_name = "insumo"
        verbose_name_plural = "insumos"
        ordering = ["nombre", "id"]
        constraints = [
            models.UniqueConstraint(Lower("nombre"), name="insumo_nombre_unico"),
            models.CheckConstraint(condition=models.Q(stock_critico__isnull=True) | (models.Q(stock_critico__gte=0) & models.Q(stock_critico__lte=models.F("stock_minimo"))), name="insumo_critico_valido"),
            models.CheckConstraint(
                condition=models.Q(existencia__gte=0),
                name="insumo_existencia_no_negativa",
                violation_error_message="La existencia no puede ser negativa.",
            ),
            models.CheckConstraint(
                condition=models.Q(stock_minimo__gte=0),
                name="insumo_minimo_no_negativo",
                violation_error_message="El stock mínimo no puede ser negativo.",
            ),
        ]

    def __str__(self):
        return self.nombre

    @property
    def bajo_minimo(self):
        return self.activo and self.existencia <= self.stock_minimo

    @property
    def nivel_stock(self):
        if not self.activo:
            return "inactivo"
        if self.existencia == 0:
            return "agotado"
        if self.stock_critico is not None and self.existencia <= self.stock_critico:
            return "critico"
        return "bajo" if self.bajo_minimo else "normal"

    @property
    def etiqueta_stock(self):
        return {"inactivo": "Inactivo", "agotado": "Agotado", "critico": "Stock crítico", "bajo": "Stock bajo", "normal": "Stock normal"}[self.nivel_stock]

    def clean(self):
        super().clean()
        if self.stock_critico is not None and self.stock_minimo is not None and not 0 <= self.stock_critico <= self.stock_minimo:
            raise ValidationError({"stock_critico": "Debe estar entre cero y el stock mínimo."})
        if self.existencia is not None and self.existencia < 0:
            raise ValidationError({"existencia": "La existencia no puede ser negativa."})
        if self.stock_minimo is not None and self.stock_minimo < 0:
            raise ValidationError({"stock_minimo": "El stock mínimo no puede ser negativo."})


class Receta(models.Model):
    producto = models.ForeignKey(
        "catalogo.Producto",
        on_delete=models.PROTECT,
        related_name="recetas",
        verbose_name="producto",
    )
    variante = models.ForeignKey(
        "catalogo.VarianteProducto",
        on_delete=models.PROTECT,
        related_name="recetas",
        verbose_name="variante",
        null=True,
        blank=True,
    )
    rendimiento = models.DecimalField(
        "rendimiento",
        max_digits=12,
        decimal_places=3,
        help_text="Cantidad de unidades del producto que produce esta receta.",
    )
    alcance = models.CharField("alcance", max_length=40, unique=True, editable=False)
    actualizada = models.DateTimeField("actualizada", auto_now=True)

    class Meta:
        verbose_name = "receta"
        verbose_name_plural = "recetas"
        ordering = ["producto__nombre", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(rendimiento__gt=0),
                name="receta_rendimiento_positivo",
                violation_error_message="El rendimiento debe ser mayor que cero.",
            ),
        ]

    def __str__(self):
        return self.producto.nombre

    def save(self, *args, **kwargs):
        if not (self.alcance or "").startswith("ejemplo:"):
            self.alcance = f"v{self.variante_id}" if self.variante_id else f"p{self.producto_id}"
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.variante_id and self.producto_id and self.variante.producto_id != self.producto_id:
            raise ValidationError("La variante no pertenece a ese producto.")
        if getattr(self.producto, "slug", "") == SLUG_ROLLITOS:
            raise ValidationError(
                "Rollitos de sabores no tiene una receta única. "
                "Configura los sabores por separado; la caja queda pendiente de resolución."
            )
        if self.rendimiento is not None and self.rendimiento <= 0:
            raise ValidationError({"rendimiento": "El rendimiento debe ser mayor que cero."})


class RecetaIngrediente(models.Model):
    receta = models.ForeignKey(
        Receta,
        on_delete=models.CASCADE,
        related_name="ingredientes",
        verbose_name="receta",
    )
    insumo = models.ForeignKey(
        Insumo,
        on_delete=models.PROTECT,
        related_name="ingredientes",
        verbose_name="insumo",
    )
    cantidad = models.DecimalField("cantidad", max_digits=12, decimal_places=3)

    class Meta:
        verbose_name = "ingrediente de receta"
        verbose_name_plural = "ingredientes de receta"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["receta", "insumo"],
                name="receta_insumo_unico",
            ),
            models.CheckConstraint(
                condition=models.Q(cantidad__gt=0),
                name="receta_cantidad_positiva",
                violation_error_message="La cantidad del ingrediente debe ser mayor que cero.",
            ),
        ]

    def __str__(self):
        return self.insumo.nombre

    def clean(self):
        super().clean()
        if self.cantidad is not None and self.cantidad <= 0:
            raise ValidationError({"cantidad": "La cantidad del ingrediente debe ser mayor que cero."})


class MovimientoInventario(models.Model):
    class Tipo(models.TextChoices):
        ENTRADA = "entrada", "Entrada"
        AJUSTE = "ajuste", "Ajuste"
        CONSUMO = "consumo", "Consumo de preparación"

    insumo = models.ForeignKey(
        Insumo,
        on_delete=models.PROTECT,
        related_name="movimientos",
        verbose_name="insumo",
    )
    pedido = models.ForeignKey(
        "pedidos.Pedido",
        on_delete=models.PROTECT,
        related_name="movimientos_inventario",
        verbose_name="pedido",
        null=True,
        blank=True,
    )
    tipo = models.CharField("tipo", max_length=20, choices=Tipo.choices)
    cantidad = models.DecimalField(
        "cantidad",
        max_digits=12,
        decimal_places=3,
        help_text="Variación aplicada. Negativa cuando la existencia disminuye.",
    )
    existencia_resultante = models.DecimalField(
        "existencia resultante",
        max_digits=12,
        decimal_places=3,
    )
    motivo = models.CharField("motivo", max_length=500)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="movimientos_inventario",
        verbose_name="responsable",
        null=True,
        blank=True,
    )
    clave = models.CharField("clave", max_length=64, unique=True, editable=False)
    creada = models.DateTimeField("fecha", auto_now_add=True)

    class Meta:
        verbose_name = "movimiento de inventario"
        verbose_name_plural = "movimientos de inventario"
        ordering = ["-creada", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(cantidad=0),
                name="movimiento_cantidad_distinta_de_cero",
                violation_error_message="El movimiento necesita una cantidad distinta de cero.",
            ),
            models.CheckConstraint(
                condition=models.Q(existencia_resultante__gte=0),
                name="movimiento_resultante_no_negativa",
                violation_error_message="La existencia no puede quedar negativa.",
            ),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} {self.insumo.nombre}"


class ConsumoPedido(models.Model):
    """Marca que el pedido ya descontó inventario una sola vez."""

    pedido = models.OneToOneField(
        "pedidos.Pedido",
        on_delete=models.PROTECT,
        related_name="consumo",
        verbose_name="pedido",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="consumos_registrados",
        verbose_name="responsable",
        null=True,
        blank=True,
    )
    creada = models.DateTimeField("fecha", auto_now_add=True)

    class Meta:
        verbose_name = "consumo de pedido"
        verbose_name_plural = "consumos de pedido"

    def __str__(self):
        return self.pedido.codigo


class Abastecimiento(models.Model):
    """Lote trazable de una entrada NUEVA. Las entradas antiguas no se reinterpretan."""
    movimiento = models.OneToOneField(MovimientoInventario, on_delete=models.PROTECT, related_name="abastecimiento")
    cantidad_inicial = models.DecimalField(max_digits=12, decimal_places=3)
    saldo = models.DecimalField(max_digits=12, decimal_places=3)
    unidad = models.CharField(max_length=20, choices=Insumo.Unidad.choices)
    es_compra = models.BooleanField(default=False)
    fecha_compra = models.DateField(null=True, blank=True)
    precio_compra = models.DecimalField("importe total de compra (CLP)", max_digits=12, decimal_places=2, null=True, blank=True)
    proveedor = models.CharField(max_length=160, blank=True)
    tipo_referencia = models.CharField(max_length=12, blank=True, choices=(("documento", "Documento de compra"), ("interna", "Referencia interna (sin documento formal)")))
    referencia_compra = models.CharField(max_length=160, blank=True)
    huella_compra = models.CharField(max_length=64, null=True, blank=True, unique=True, editable=False)
    caducidad = models.DateField(null=True, blank=True)
    lote = models.CharField(max_length=100, blank=True)
    observaciones = models.CharField(max_length=1000, blank=True)

    class Meta:
        ordering = ["-movimiento__creada", "-pk"]
        constraints = [
            models.CheckConstraint(condition=models.Q(cantidad_inicial__gt=0) & models.Q(saldo__gte=0) & models.Q(saldo__lte=models.F("cantidad_inicial")), name="abastecimiento_saldo_valido"),
            models.CheckConstraint(condition=models.Q(precio_compra__isnull=True) | models.Q(precio_compra__gte=0), name="abastecimiento_precio_valido"),
            models.CheckConstraint(condition=models.Q(es_compra=True) | (models.Q(fecha_compra__isnull=True) & models.Q(precio_compra__isnull=True)), name="abastecimiento_datos_compra"),
        ]

    def clean(self):
        super().clean()
        if self.movimiento_id and self.movimiento.tipo != MovimientoInventario.Tipo.ENTRADA:
            raise ValidationError("Solo una entrada puede generar abastecimiento.")
        if not self.es_compra and (self.fecha_compra is not None or self.precio_compra is not None):
            raise ValidationError("Marca como compra para registrar fecha o importe de compra.")


class SalidaLote(models.Model):
    """Vincula un descuento existente con el saldo del lote usado (FEFO)."""
    abastecimiento = models.ForeignKey(Abastecimiento, on_delete=models.PROTECT, related_name="salidas")
    movimiento = models.ForeignKey(MovimientoInventario, on_delete=models.PROTECT, related_name="salidas_lote")
    cantidad = models.DecimalField(max_digits=12, decimal_places=3)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["abastecimiento", "movimiento"], name="salida_lote_movimiento_unico"), models.CheckConstraint(condition=models.Q(cantidad__gt=0), name="salida_lote_positiva")]
