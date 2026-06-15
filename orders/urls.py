from django.urls import path
from . import views
urlpatterns = [
    path("cart/", views.CartView.as_view(), name="cart"),
    path("cart/add/", views.CartAddView.as_view(), name="cart-add"),
    path("cart/remove/<int:item_id>/", views.CartRemoveView.as_view(), name="cart-remove"),
    path("checkout/", views.CheckoutView.as_view(), name="checkout"),
    path("orders/", views.OrderListView.as_view(), name="order-list"),
    path("orders/<int:pk>/", views.OrderDetailView.as_view(), name="order-detail"),
    path("orders/<int:pk>/status/", views.OrderStatusUpdateView.as_view(), name="order-status"),
    path("orders/admin/", views.AdminOrderListView.as_view(), name="admin-order-list"),
    path("print/order/<int:order_id>/", views.print_order, name="print-order"),
    path("print/invoice/<int:order_id>/", views.print_invoice, name="print-invoice"),
    path("send/invoice/<int:order_id>/", views.send_invoice, name="send-invoice"),
]
