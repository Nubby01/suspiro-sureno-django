from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ("username", "email", "rol", "is_staff", "is_superuser")
    fieldsets = UserAdmin.fieldsets[:2] + (
        ("Suspiro Sureño", {"fields": ("rol", "telefono")}),
    ) + UserAdmin.fieldsets[2:]
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Suspiro Sureño", {"fields": ("rol", "telefono", "email")}),
    )

    def _es_superusuario(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_module_permission(self, request):
        return self._es_superusuario(request)

    def has_view_permission(self, request, obj=None):
        return self._es_superusuario(request)

    def has_add_permission(self, request):
        return self._es_superusuario(request)

    def has_change_permission(self, request, obj=None):
        return self._es_superusuario(request)

    def has_delete_permission(self, request, obj=None):
        return self._es_superusuario(request)
