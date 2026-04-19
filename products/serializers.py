from rest_framework import serializers
from .models import PokemonProduct, Category, PokemonType, Era, CardSet


class EraSerializer(serializers.ModelSerializer):
    class Meta:
        model = Era
        fields = ["id", "code", "name"]


class CardSetSerializer(serializers.ModelSerializer):
    era = EraSerializer(read_only=True)

    class Meta:
        model = CardSet
        fields = ["id", "code", "name", "era", "symbol_url", "logo_url", "total_cards", "release_date"]


class PokemonTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PokemonType
        fields = ["id", "name"]


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug"]


class PokemonProductSerializer(serializers.ModelSerializer):
    pokemon_types = PokemonTypeSerializer(many=True, read_only=True)
    category = CategorySerializer(read_only=True)
    card_set = CardSetSerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), source="category", write_only=True, required=False
    )
    card_set_id = serializers.PrimaryKeyRelatedField(
        queryset=CardSet.objects.all(), source="card_set", write_only=True, required=False
    )
    pokemon_type_ids = serializers.PrimaryKeyRelatedField(
        queryset=PokemonType.objects.all(), source="pokemon_types",
        write_only=True, many=True, required=False
    )
    in_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = PokemonProduct
        fields = [
            "pb_id", "sku", "tcgplayer_id", "gengar_id",
            "id", "name", "name_japanese", "description", "flavour_text",
            "category", "category_id", "card_set", "card_set_id",
            "pokemon_types", "pokemon_type_ids",
            "rarity", "pokedex_number", "card_number", "variant_override",
            "supertype", "card_subtypes", "hp", "artist",
            "weakness_type", "weakness_value",
            "resistance_type", "resistance_value", "retreat_cost",
            "ability_name", "ability_type", "ability_text",
            "attack_1_name", "attack_1_damage", "attack_1_text",
            "attack_2_name", "attack_2_damage", "attack_2_text",
            "image", "image_url", "image_small_url",
            "price", "price_normal", "price_holo",
            "price_reverse_holo", "price_first_edition",
            "stock", "in_stock", "is_active",
            "created_at", "updated_at",
        ]
        read_only_fields = ["pb_id", "sku", "id", "created_at", "updated_at"]