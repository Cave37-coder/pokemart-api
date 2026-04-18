from django.urls import path
from . import views

urlpatterns = [
    path('initiate/', views.PayFastInitView.as_view(), name='payfast-init'),
    path('itn/', views.PayFastITNView.as_view(), name='payfast-itn'),
]