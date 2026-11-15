import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import PokemonProduct

blank = PokemonProduct.objects.filter(is_active=True, pokedex_number__isnull=True, supertype='')
total_blank = blank.count()
has_hp = blank.exclude(hp__isnull=True).count()
no_hp = total_blank - has_hp

print(f"supertype blank AND pokedex_number null: {total_blank}")
print(f"  of those, hp IS set (almost certainly real Pokemon cards): {has_hp}")
print(f"  of those, hp is NOT set (likely Trainer/Energy/non-Pokemon): {no_hp}")

print("\nSample of 15 blank-supertype rows WITH hp set (should be Pokemon):")
for p in blank.exclude(hp__isnull=True)[:15]:
    print(f"  id={p.id} {p.name!r} hp={p.hp} set={p.card_set.code if p.card_set else '?'}")

print("\nSample of 15 blank-supertype rows WITHOUT hp set:")
for p in blank.filter(hp__isnull=True)[:15]:
    print(f"  id={p.id} {p.name!r} set={p.card_set.code if p.card_set else '?'}")
