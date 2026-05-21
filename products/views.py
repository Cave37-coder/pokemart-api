from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import rest_framework as django_filters
from .models import PokemonProduct, Category, PokemonType
from .serializers import PokemonProductSerializer, CategorySerializer, PokemonTypeSerializer


class PokemonProductFilter(django_filters.FilterSet):
    era = django_filters.CharFilter(field_name='card_set__era__code', lookup_expr='iexact')
    card_set = django_filters.CharFilter(field_name='card_set__code', lookup_expr='iexact')
    energy_type = django_filters.CharFilter(field_name='pokemon_types__name', lookup_expr='iexact')
    supertype = django_filters.CharFilter(field_name='supertype', lookup_expr='icontains')
    rarity = django_filters.CharFilter(field_name='rarity', lookup_expr='iexact')
    subtype = django_filters.CharFilter(field_name='card_subtypes', lookup_expr='icontains')
    min_price = django_filters.NumberFilter(field_name='price', lookup_expr='gte')
    max_price = django_filters.NumberFilter(field_name='price', lookup_expr='lte')
    in_stock = django_filters.BooleanFilter(field_name='stock', method='filter_in_stock')

    def filter_in_stock(self, queryset, name, value):
        if value:
            return queryset.filter(stock__gt=0)
        return queryset

    class Meta:
        model = PokemonProduct
        fields = ['era', 'card_set', 'energy_type', 'supertype', 'rarity', 'category', 'min_price', 'max_price', 'in_stock', 'subtype']


class PokemonProductViewSet(viewsets.ModelViewSet):
    queryset = PokemonProduct.objects.filter(is_active=True).select_related(
        'category', 'card_set', 'card_set__era'
    ).prefetch_related('pokemon_types')
    serializer_class = PokemonProductSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = PokemonProductFilter
    search_fields = ['name', 'card_set__name', 'description']
    ordering_fields = ['price', 'created_at', 'name', 'card_number', 'pokedex_number']
    ordering = ['-card_set__release_date', 'card_number']

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




