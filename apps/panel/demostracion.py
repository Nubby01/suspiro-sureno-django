"""Oculta solo marcadores inequívocos; nunca cambia ni elimina registros."""
from django.db.models import Q
from apps.cuentas.models import Usuario
CUENTAS_DEMO = ("demo-administradora", "demo-ayudante", "demo-clienta")
def criterio_demo(campo):
    return Q(**{campo+"__istartswith":"DEMO · "}) | Q(**{campo+"__istartswith":"Ejemplo de prueba"})

def filtro_demo(consulta, request, campo="nombre"):
    usuario = request.user
    puede = usuario.is_authenticated and (usuario.is_superuser or usuario.rol == Usuario.Rol.ADMINISTRADORA)
    if puede and request.GET.get("incluir_demo") == "1":
        return consulta
    if campo == "username":
        return consulta.exclude(username__in=CUENTAS_DEMO)
    return consulta.exclude(criterio_demo(campo))
