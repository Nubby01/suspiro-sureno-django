from django.db import models
from django.db.models.functions import Lower


class Categoria(models.Model):
    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField("nombre", max_length=80)
    slug = models.SlugField("slug", unique=True)
    descripcion = models.TextField("descripción", blank=True)
    orden = models.PositiveIntegerField("orden", default=0)
    activa = models.BooleanField("activa", default=True)

    class Meta:
        verbose_name = "categoría"
        verbose_name_plural = "categorías"
        ordering = ["orden", "nombre"]

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    id = models.BigAutoField(primary_key=True)
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.PROTECT,
        related_name="productos",
        verbose_name="categoría",
    )
    nombre = models.CharField("nombre", max_length=120)
    slug = models.SlugField("slug", unique=True)
    descripcion = models.TextField("descripción", blank=True)
    referencia_imagen = models.CharField(
        "referencia de imagen",
        max_length=255,
        blank=True,
        help_text="Ruta relativa reservada. El almacenamiento de imágenes todavía no está configurado.",
    )
    activo = models.BooleanField("activo", default=True)

    class Meta:
        verbose_name = "producto"
        verbose_name_plural = "productos"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class VarianteProducto(models.Model):
    id = models.BigAutoField(primary_key=True)
    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name="variantes",
        verbose_name="producto",
    )
    nombre = models.CharField("nombre", max_length=80, blank=True)
    precio = models.DecimalField(
        "precio minorista",
        max_digits=10,
        decimal_places=0,
        null=True,
        blank=True,
        help_text=(
            "Precio público. Vacío significa que el precio está pendiente de consulta. "
            "Un cero es un precio confirmado de $0, no un precio desconocido."
        ),
    )
    precio_mayorista = models.DecimalField(
        "precio mayorista",
        max_digits=10,
        decimal_places=0,
        null=True,
        blank=True,
        help_text=(
            "Uso interno de la administradora. No se publica, no se envía al navegador "
            "y no se aplica automáticamente por la cantidad."
        ),
    )
    es_predeterminada = models.BooleanField("predeterminada", default=False)
    orden = models.PositiveIntegerField("orden", default=0)
    activa = models.BooleanField("activa", default=True)

    class Meta:
        verbose_name = "variante de producto"
        verbose_name_plural = "variantes de producto"
        ordering = ["orden", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(precio__gte=0) | models.Q(precio__isnull=True),
                name="precio_variante_no_negativo",
                violation_error_message="El precio no puede ser negativo.",
            ),
            models.CheckConstraint(
                condition=models.Q(precio_mayorista__gte=0) | models.Q(precio_mayorista__isnull=True),
                name="precio_mayorista_no_negativo",
                violation_error_message="El precio mayorista no puede ser negativo.",
            ),
            models.UniqueConstraint(
                fields=["producto"],
                condition=models.Q(es_predeterminada=True),
                name="una_predeterminada_por_producto",
                violation_error_message="Solo una variante puede ser la predeterminada del producto.",
            ),
            models.UniqueConstraint(
                Lower("nombre"),
                "producto",
                name="nombre_variante_unico_por_producto",
                violation_error_message="Ya existe una variante con ese nombre en el producto.",
            ),
        ]

    def clean(self):
        super().clean()
        self.nombre = (self.nombre or "").strip()

    def __str__(self):
        nombre = (self.nombre or "").strip()
        if nombre:
            return nombre
        if self.producto_id:
            return self.producto.nombre
        return "Variante sin nombre"


class ElementoGaleria(models.Model):
    """Fotografía de la galería de un producto.

    Si hay un producto de origen, se reutilizan su nombre y su fotografía.
    No se duplica el archivo ni se crea una variante comercial.
    """

    id = models.BigAutoField(primary_key=True)
    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name="galeria",
        verbose_name="producto",
    )
    producto_origen = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name="apariciones_en_galerias",
        verbose_name="producto de origen",
        null=True,
        blank=True,
    )
    nombre = models.CharField(
        "nombre del sabor",
        max_length=120,
        blank=True,
        help_text="Opcional si el nombre sale del producto de origen.",
    )
    referencia_imagen = models.CharField(
        "referencia de imagen",
        max_length=255,
        blank=True,
        help_text="Opcional si la fotografía sale del producto de origen.",
    )
    orden = models.PositiveIntegerField("orden", default=0)

    class Meta:
        verbose_name = "elemento de galería"
        verbose_name_plural = "elementos de galería"
        ordering = ["orden", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["producto", "producto_origen"],
                condition=models.Q(producto_origen__isnull=False),
                name="origen_unico_en_galeria",
                violation_error_message="Ese sabor ya está en la galería del producto.",
            ),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError

        from .imagenes import validar_referencia

        super().clean()
        self.nombre = (self.nombre or "").strip()
        self.referencia_imagen = (self.referencia_imagen or "").strip()
        if (
            self.producto_id
            and self.producto_origen_id
            and self.producto_id == self.producto_origen_id
        ):
            raise ValidationError("Un producto no puede incluirse como sabor de sí mismo.")
        if self.referencia_imagen:
            self.referencia_imagen = validar_referencia(self.referencia_imagen)
        nombre_visible = self.nombre
        if not nombre_visible and self.producto_origen_id:
            nombre_visible = (self.producto_origen.nombre or "").strip()
        if not nombre_visible:
            raise ValidationError("Indica el nombre del sabor o un producto de origen.")
        tiene_foto = bool(self.referencia_imagen)
        if not tiene_foto and self.producto_origen_id:
            tiene_foto = bool((self.producto_origen.referencia_imagen or "").strip())
        if not tiene_foto:
            raise ValidationError(
                "Indica una fotografía o un producto de origen que ya tenga la suya."
            )

    def __str__(self):
        if self.nombre:
            return self.nombre
        if self.producto_origen_id:
            return self.producto_origen.nombre
        return "Elemento de galería"
