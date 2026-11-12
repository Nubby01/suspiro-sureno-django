from django.db import migrations
from django.db.models import F


def reconocer_ventas(apps, schema_editor):
    Pedido = apps.get_model("pedidos", "Pedido")
    Evento = apps.get_model("pedidos", "EventoPedido")
    Venta = apps.get_model("pedidos", "VentaPedido")
    alias = schema_editor.connection.alias
    for pedido in Pedido.objects.using(alias).all().iterator():
        evento = Evento.objects.using(alias).filter(pedido_id=pedido.pk,
            estado_nuevo__in=("recibido", "entregado")).exclude(
                estado_anterior=F("estado_nuevo")).order_by("creada", "pk").first()
        # La ruta normal crea todos los pedidos en Recibido. Para registros
        # anteriores sin historial se indica explícitamente la fecha estimada.
        if evento is None and pedido.estado not in ("recibido", "en_preparacion", "listo", "entregado"):
            continue
        Venta.objects.using(alias).get_or_create(pedido_id=pedido.pk, defaults={
            "total": pedido.total, "fecha": evento.creada if evento else pedido.creada,
            "usuario_id": evento.usuario_id if evento else None,
            "estado_origen": evento.estado_nuevo if evento else "entregado" if pedido.estado == "entregado" else "recibido",
            "fecha_estimada": evento is None,
        })


class Migration(migrations.Migration):
    dependencies = [("pedidos", "0003_ventapedido")]
    operations = [migrations.RunPython(reconocer_ventas, migrations.RunPython.noop)]
