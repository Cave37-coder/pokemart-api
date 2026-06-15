# Run: python manage.py shell
# Then paste this block:

from products.models import PokemonProduct, CardSet
import inspect

print("=== PokemonProduct fields ===")
for f in PokemonProduct._meta.get_fields():
    print(f"  {f.name:30s} {type(f).__name__}")

print()
print("=== CardSet fields ===")
for f in CardSet._meta.get_fields():
    print(f"  {f.name:30s} {type(f).__name__}")

print()
# Check variant_override specifically
try:
    f = PokemonProduct._meta.get_field("variant_override")
    print(f"variant_override: {type(f).__name__} ✓")
except Exception as e:
    print(f"variant_override MISSING: {e}")

try:
    f = PokemonProduct._meta.get_field("price_zar")
    print(f"price_zar:        {type(f).__name__} ✓")
except Exception as e:
    print(f"price_zar MISSING — need to add DecimalField to model: {e}")

try:
    f = PokemonProduct._meta.get_field("card_number")
    print(f"card_number:      {type(f).__name__} ✓")
except Exception as e:
    print(f"card_number MISSING: {e}")
