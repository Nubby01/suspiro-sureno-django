from django.urls import path

from .api import CuentaApiView, TokenIngresoView, TokenRenovarView

urlpatterns = [
    path("api/token/", TokenIngresoView.as_view(), name="api_token"),
    path("api/token/refresh/", TokenRenovarView.as_view(), name="api_token_renovar"),
    path("api/cuenta/", CuentaApiView.as_view(), name="api_cuenta"),
]
