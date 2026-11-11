from django.conf import settings
from django.db import models

from apps.catalogo.consultas import formato_clp
from apps.cotizaciones.models import codigo_publico


class Pedido(models.Model):
    class Estado(models.TextChoices):
        RECIBIDO = "recibido", "Recibido"
        EN_PREPARACION = "en_preparacion", "En preparación"
        LISTO = "listo", "Listo"
        ENTREGADO = "entregado", "Entregado"
        CANCELADO = "cancelado", "Cancelado"

    codigo = models.CharField("código", max_length=20, unique=True, editable=False)
    cotizacion = models.OneToOneField(
        "cotizaciones.Cotizacion",
        on_delete=models.PROTECT,
        related_name="pedido",
        verbose_name="cotización",
    )
    cliente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="pedidos",
        verbose_name="clienta",
        null=True,
        blank=True,
    )
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="pedidos_asignados", limit_choices_to={"rol": "ayudante", "is_active": True})
    nombre = models.CharField("nombre", max_length=120)
    correo = models.EmailField("correo")
    telefono = models.CharField("teléfono", max_length=20)
    total = models.DecimalField("total confirmado", max_digits=12, decimal_places=0)
    creada = models.DateTimeField("fecha de creación", auto_now_add=True)
    estado = models.CharField(
        "estado",
        max_length=20,
        choices=Estado.choices,
        default=Estado.RECIBIDO,
    )

    class Meta:
        verbose_name = "pedido"
        verbose_name_plural = "pedidos"
        ordering = ["-creada", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(total__gte=0),
                name="total_pedido_no_negativo",
                violation_error_message="El total no puede ser negativo.",
            ),
        ]

    def __str__(self):
        return self.codigo

    def save(self, *args, **kwargs):
        if not self.codigo:
            for _ in range(5):
                candidato = codigo_publico("PED")
                if not Pedido.objects.filter(codigo=candidato).exists():
                    self.codigo = candidato
                    break
            if not self.codigo:
                from django.core.exceptions import ValidationError

                raise ValidationError("No se pudo crear el identificador del pedido.")
        super().save(*args, **kwargs)

    def total_texto(self):
        return formato_clp(self.total)


class LineaPedido(models.Model):
    pedido = models.ForeignKey(
        Pedido,
        on_delete=models.CASCADE,
        related_name="lineas",
        verbose_name="pedido",
    )
    variante = models.ForeignKey(
        "catalogo.VarianteProducto",
        on_delete=models.PROTECT,
        related_name="lineas_pedido",
        verbose_name="variante",
    )
    nombre_producto = models.CharField("producto", max_length=120)
    nombre_variante = models.CharField("variante", max_length=80, blank=True)
    detalle = models.CharField("detalle", max_length=255, blank=True)
    cantidad = models.PositiveIntegerField("cantidad")
    precio_acordado = models.DecimalField("precio acordado", max_digits=10, decimal_places=0)

    class Meta:
        verbose_name = "línea de pedido"
        verbose_name_plural = "líneas de pedido"
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(cantidad__gte=1) & models.Q(cantidad__lte=99),
                name="cantidad_pedido_valida",
                violation_error_message="La cantidad debe estar entre 1 y 99.",
            ),
            models.CheckConstraint(
                condition=models.Q(precio_acordado__gte=0),
                name="precio_pedido_no_negativo",
                violation_error_message="El precio no puede ser negativo.",
            ),
        ]

    def __str__(self):
        return self.nombre_producto

    def importe_texto(self):
        return formato_clp(self.precio_acordado * self.cantidad)

    def precio_texto(self):
        return formato_clp(self.precio_acordado)


class EventoPedido(models.Model):
    pedido = models.ForeignKey(
        Pedido,
        on_delete=models.CASCADE,
        related_name="eventos",
        verbose_name="pedido",
    )
    estado_anterior = models.CharField("estado anterior", max_length=20, blank=True)
    estado_nuevo = models.CharField("estado nuevo", max_length=20)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="eventos_pedido",
        verbose_name="responsable",
        null=True,
        blank=True,
    )
    nota = models.CharField("nota", max_length=500, blank=True)
    creada = models.DateTimeField("fecha", auto_now_add=True)

    class Meta:
        verbose_name = "cambio de pedido"
        verbose_name_plural = "cambios de pedido"
        ordering = ["creada", "id"]

    def __str__(self):
        return f"{self.pedido.codigo}: {self.estado_nuevo}"

    def etiqueta_estado(self):
        return dict(Pedido.Estado.choices).get(self.estado_nuevo, self.estado_nuevo)
