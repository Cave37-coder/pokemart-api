from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register('products', views.PokemonProductViewSet, basename='product')
router.register('categories', views.CategoryViewSet, basename='category')
router.register('types', views.PokemonTypeViewSet, basename='type')

urlpatterns = router.urls