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
    path("stock/bundles/", views.bundle_stock_entry, name="bundle-stock-entry"),
    path("stock/update/", views.stock_update, name="stock-update"),
    path("stock/wipe/", views.stock_wipe, name="stock-wipe"),
    path("stock/print/", views.stock_print, name="stock-print"),
    path("stock/dividers/", views.stock_dividers, name="stock-dividers"),
    path("stock/played/", views.stock_add_played, name="stock-add-played"),
    path("sets/", views.sets_list, name="sets-list"),
    path('stock/delete/<int:product_id>/', views.delete_product, name='stock_delete'),
    path("checklists/stock-check/", views.checklist_stock, name="checklist-stock"),
    path("manage/", views.manage_set, name="manage-set"),
]
