"""Centros del alfajor brownie. No son productos ni precios distintos."""

SLUG = "alfajor-brownie-con-relleno"
SABORES = (
    ("cafe", "Café"),
    ("menta", "Menta"),
    ("limon", "Limón"),
    ("chocolate", "Chocolate"),
    ("frambuesa", "Frambuesa"),
)
NOMBRES = {codigo: nombre for codigo, nombre in SABORES}
