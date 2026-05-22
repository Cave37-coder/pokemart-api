from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PokemonProductViewSet, CategoryViewSet, PokemonTypeViewSet
from . import views

router = DefaultRouter()
router.register(r"products", PokemonProductViewSet, basename="product")
router.register(r"categories", CategoryViewSet, basename="category")
router.register(r"pokemon-types", PokemonTypeViewSet, basename="pokemon-type")

urlpatterns = [
    path("", include(router.urls)),
    path("stock/entry/", views.stock_entry, name="stock-entry"),
    path("stock/update/", views.stock_update, name="stock-update"),
    path("stock/wipe/", views.stock_wipe, name="stock-wipe"),
]
