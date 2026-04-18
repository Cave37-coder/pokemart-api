from rest_framework import serializers
from .models import PokemonProduct, Category, PokemonType


class PokemonTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PokemonType
        fields = ['id', 'name']


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug']


class PokemonProductSerializer(serializers.ModelSerializer):
    pokemon_types = PokemonTypeSerializer(many=True, read_only=True)
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), source='category', write_only=True, required=False
    )
    pokemon_type_ids = serializers.PrimaryKeyRelatedField(
        queryset=PokemonType.objects.all(), source='pokemon_types',
        write_only=True, many=True, required=False
    )
    in_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = PokemonProduct
        fields = [
            'id', 'name', 'description', 'category', 'category_id',
            'pokemon_types', 'pokemon_type_ids', 'rarity', 'set_name',
            'price', 'stock', 'in_stock', 'image', 'is_active',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']