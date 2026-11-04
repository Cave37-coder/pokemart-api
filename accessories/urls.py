from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AccessoryViewSet
from . import sealed_collection

router = DefaultRouter()
router.register(r"accessories", AccessoryViewSet, basename="accessory")

urlpatterns = [
    path("sealed-collection/", sealed_collection.sealed_list, name="sealed-collection"),
    path("sealed-collection/search/", sealed_collection.sealed_search, name="sealed-collection-search"),
    path("sealed-collection/items/", sealed_collection.sealed_add, name="sealed-collection-add"),
    path("sealed-collection/items/<int:item_id>/", sealed_collection.sealed_item, name="sealed-collection-item"),
    path("", include(router.urls)),
]
