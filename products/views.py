from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from .models import PokemonProduct, Category, PokemonType
from .serializers import PokemonProductSerializer, CategorySerializer, PokemonTypeSerializer


class PokemonProductViewSet(viewsets.ModelViewSet):
    queryset = PokemonProduct.objects.filter(is_active=True).select_related(
        'category', 'card_set', 'card_set__era'
    ).prefetch_related('pokemon_types')
    serializer_class = PokemonProductSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = {
        'rarity': ['exact'],
        'category': ['exact'],
        'pokemon_types': ['exact'],
        'pokemon_types__name': ['exact'],
        'is_active': ['exact'],
        'card_set__code': ['exact'],
        'card_set__era__code': ['exact'],
    }
    search_fields = ['name', 'card_set__name', 'description']
    ordering_fields = ['price', 'created_at', 'name', 'card_number']
    ordering = ['card_set__code', 'card_number']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [IsAuthenticatedOrReadOnly()]


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [IsAuthenticatedOrReadOnly()]


class PokemonTypeViewSet(viewsets.ModelViewSet):
    queryset = PokemonType.objects.all()
    serializer_class = PokemonTypeSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [IsAuthenticatedOrReadOnly()]
