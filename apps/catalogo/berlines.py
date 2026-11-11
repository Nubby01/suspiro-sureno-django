"""Sabores de la caja de berlines. No son productos ni precios distintos."""

SLUG = "berlines"
PRESENTACION = "Caja de 4"
SABORES = (
    ("manjar", "Manjar"),
    ("pastelera", "Pastelera"),
    ("membrillo", "Membrillo"),
    ("chocolate", "Chocolate"),
)
NOMBRES = {codigo: nombre for codigo, nombre in SABORES}
