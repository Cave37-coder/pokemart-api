from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AccessoryViewSet

router = DefaultRouter()
router.register(r"accessories", AccessoryViewSet, basename="accessory")

urlpatterns = [
    path("", include(router.urls)),
]
