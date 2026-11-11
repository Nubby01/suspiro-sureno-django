from django.contrib.admin.apps import AdminConfig


class AdminSuspiroConfig(AdminConfig):
    default_site = "apps.cuentas.sitio_admin.SitioAdmin"
