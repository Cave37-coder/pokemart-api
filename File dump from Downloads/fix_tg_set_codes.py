# fix_tg_set_codes.py
# Moves BST records -> BRSTG and ST records -> SITTG
# Run with DATABASE_URL uncommented in .env
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import PokemonProduct, CardSet

fixes = [
    ('BST',  'BRSTG', 'Brilliant Stars Trainer Gallery'),
    ('ST',   'SITTG', 'Silver Tempest Trainer Gallery'),
]

for from_code, to_code, set_name in fixes:
    try:
        from_set = CardSet.objects.get(code=from_code)
        to_set   = CardSet.objects.get(code=to_code)
    except CardSet.DoesNotExist as e:
        print(f"ERROR: {e}")
        continue

    count = PokemonProduct.objects.filter(card_set=from_set).count()
    print(f"\n{from_code} -> {to_code} ({set_name})")
    print(f"  Records to move: {count}")

    # Show sample before moving
    for p in PokemonProduct.objects.filter(card_set=from_set)[:3]:
        print(f"  Sample: #{p.card_number} {p.name[:40]} | {p.variant_override}")

    if count == 0:
        print(f"  Nothing to move")
        continue

    # Move records
    moved = PokemonProduct.objects.filter(card_set=from_set).update(card_set=to_set)
    print(f"  Moved: {moved} records")

    # Verify
    after_from = PokemonProduct.objects.filter(card_set=from_set).count()
    after_to   = PokemonProduct.objects.filter(card_set=to_set).count()
    print(f"  {from_code} now has: {after_from} records")
    print(f"  {to_code} now has:  {after_to} records")

print("\nDone.")
