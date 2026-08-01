"""
diagnose_order_132_lookups.py

Read-only. Figures out why recreate_order_132.py's lookups failed for the
"Normal" variant items (0 matches) and PRE #33 (3 matches), by printing
every PokemonProduct row that exists for those cards -- variant_override,
condition, stock, is_active -- exactly as stored, no guessing.

Usage:
    python manage.py shell -c "exec(open('diagnose_order_132_lookups.py').read())"
"""

from products.models import PokemonProduct

PROBLEM_CARDS = [
    ("ASC", 81), ("ASC", 85),
    ("ASR", 9), ("ASR", 90),
    ("JTG", 15), ("JTG", 130),
    ("LOR", 142),
    ("OBF", 21),
    ("PAL", 14),
    ("PAR", 138),
    ("PRE", 33),
    ("MEW", 133),
    ("SSP", 143),
    ("SM9", 79), ("SM9", 80),
    ("SM11", 157),
]

for set_code, card_number in PROBLEM_CARDS:
    print(f"\n[{set_code} #{card_number}]")
    rows = PokemonProduct.objects.filter(card_set__code=set_code, card_number=card_number)
    if not rows:
        print("  NO ROWS AT ALL for this set_code+card_number -- check the set code / number itself.")
        continue
    for p in rows:
        print(f"  id={p.id} name={p.name!r} variant_override={p.variant_override!r} "
              f"condition={p.condition!r} rarity={p.rarity!r} stock={p.stock} "
              f"is_active={p.is_active} price={p.price}")
