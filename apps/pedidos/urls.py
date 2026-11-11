from django.urls import path

from .views import DetallePedidoView, ListaPedidosView, MisPedidosView

urlpatterns = [
    path("cuenta/pedidos/", MisPedidosView.as_view(), name="mis_pedidos"),
    path("cuenta/gestion/pedidos/", ListaPedidosView.as_view(), name="pedidos_gestion"),
    path("cuenta/gestion/pedidos/<str:codigo>/", DetallePedidoView.as_view(), name="pedido_gestion"),
]
