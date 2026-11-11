from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AccessoryViewSet
from . import sealed_collection, staff_api

router = DefaultRouter()
router.register(r"accessories", AccessoryViewSet, basename="accessory")

urlpatterns = [
    path("sealed-collection/", sealed_collection.sealed_list, name="sealed-collection"),
    path("sealed-collection/sets/", sealed_collection.sealed_sets, name="sealed-collection-sets"),
    path("sealed-collection/search/", sealed_collection.sealed_search, name="sealed-collection-search"),
    path("sealed-collection/items/", sealed_collection.sealed_add, name="sealed-collection-add"),
    path("sealed-collection/items/<int:item_id>/", sealed_collection.sealed_item, name="sealed-collection-item"),
    path("accessories-admin/", staff_api.staff_accessories, name="accessories-admin"),
    path("accessories-admin/<int:pk>/", staff_api.staff_accessory_detail, name="accessories-admin-detail"),
    path("", include(router.urls)),
]
