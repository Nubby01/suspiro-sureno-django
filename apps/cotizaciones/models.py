import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.catalogo.consultas import formato_clp


def codigo_publico(prefijo):
    return f"{prefijo}-{secrets.token_hex(4).upper()}"


def token_consulta():
    return secrets.token_urlsafe(32)


class Cotizacion(models.Model):
    class Estado(models.TextChoices):
        SOLICITADA = "solicitada", "Solicitada"
        EN_REVISION = "en_revision", "En revisión"
        CONFIRMADA = "confirmada", "Confirmada"
        RECHAZADA = "rechazada", "Rechazada"
        CANCELADA = "cancelada", "Cancelada"
        CONVERTIDA = "convertida", "Convertida en pedido"

    ABIERTAS = (Estado.SOLICITADA, Estado.EN_REVISION)
    codigo = models.CharField("código", max_length=20, unique=True, editable=False)
    token = models.CharField("enlace privado", max_length=64, unique=True, editable=False)
    creada = models.DateTimeField("fecha de creación", auto_now_add=True)
    estado = models.CharField(
        "estado",
        max_length=20,
        choices=Estado.choices,
        default=Estado.SOLICITADA,
    )
    cliente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="cotizaciones",
        verbose_name="clienta",
        null=True,
        blank=True,
    )
    nombre = models.CharField("nombre", max_length=120)
    correo = models.EmailField("correo")
    telefono = models.CharField("teléfono", max_length=20)
    observaciones = models.TextField("observaciones", blank=True)
    motivo = models.CharField("motivo", max_length=500, blank=True)

    class Meta:
        verbose_name = "cotización"
        verbose_name_plural = "cotizaciones"
        ordering = ["-creada", "-id"]

    def __str__(self):
        return self.codigo

    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = self._identificador_libre(codigo_publico, "COT")
        if not self.token:
            self.token = self._identificador_libre(lambda _prefijo: token_consulta(), "")
        super().save(*args, **kwargs)

    def _identificador_libre(self, generador, prefijo):
        for _ in range(5):
            candidato = generador(prefijo) if prefijo else generador("")
            campo = "codigo" if prefijo else "token"
            if not Cotizacion.objects.filter(**{campo: candidato}).exists():
                return candidato
        raise ValidationError("No se pudo crear el identificador. Intenta nuevamente.")

    def total(self):
        lineas = list(self.lineas.all())
        if not lineas or any(linea.precio_acordado is None for linea in lineas):
            return None
        return sum((linea.precio_acordado * linea.cantidad for linea in lineas), start=0)

    def total_texto(self):
        total = self.total()
        if total is None:
            return "Total pendiente"
        return formato_clp(total)


class LineaCotizacion(models.Model):
    cotizacion = models.ForeignKey(
        Cotizacion,
        on_delete=models.CASCADE,
        related_name="lineas",
        verbose_name="cotización",
    )
    variante = models.ForeignKey(
        "catalogo.VarianteProducto",
        on_delete=models.PROTECT,
        related_name="lineas_cotizacion",
        verbose_name="variante",
    )
    nombre_producto = models.CharField("producto", max_length=120)
    nombre_variante = models.CharField("variante", max_length=80, blank=True)
    detalle = models.CharField("detalle", max_length=255, blank=True)
    cantidad = models.PositiveIntegerField("cantidad")
    precio_acordado = models.DecimalField(
        "precio acordado",
        max_digits=10,
        decimal_places=0,
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "línea de cotización"
        verbose_name_plural = "líneas de cotización"
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(cantidad__gte=1) & models.Q(cantidad__lte=99),
                name="cantidad_cotizacion_valida",
                violation_error_message="La cantidad debe estar entre 1 y 99.",
            ),
            models.CheckConstraint(
                condition=models.Q(precio_acordado__gte=0) | models.Q(precio_acordado__isnull=True),
                name="precio_cotizacion_no_negativo",
                violation_error_message="El precio no puede ser negativo.",
            ),
        ]

    def __str__(self):
        return self.nombre_producto

    def precio_texto(self):
        if self.precio_acordado is None:
            return "Consultar precio"
        return formato_clp(self.precio_acordado)

    def importe(self):
        if self.precio_acordado is None:
            return None
        return self.precio_acordado * self.cantidad

    def importe_texto(self):
        importe = self.importe()
        if importe is None:
            return "Pendiente"
        return formato_clp(importe)
