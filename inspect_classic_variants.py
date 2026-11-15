import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from collections import defaultdict
from products.models import PokemonProduct, CardSet

# Read-only. list_classic_sets.py showed AQ/EX/LC/SK/TRR with roughly 2x the
# card count Serebii's own set pages list (e.g. AQ=322 vs Serebii's Aquapolis
# =186, LC=216 vs Serebii's Legendary=110, TRR=220 vs Serebii's EX Team Rocket
# Returns=111). Before building the fetch script, need to know WHY: are these
# duplicate rows for the same printed card (edition/holo variants -- safe,
# both get the same correct image) or genuinely different numbering that
# would need separate handling?

CODES = ['AQ', 'EX', 'LC', 'SK', 'TRR', 'BS2', 'BSS']

for code in CODES:
    try:
        cs = CardSet.objects.get(code=code)
    except CardSet.DoesNotExist:
        print(f"=== {code}: not found ===")
        continue
    products = list(PokemonProduct.objects.filter(card_set=cs, is_active=True).values('id', 'name', 'card_number'))
    by_number = defaultdict(list)
    for p in products:
        by_number[p['card_number']].append(p)

    dupe_numbers = {n: rows for n, rows in by_number.items() if len(rows) > 1}
    print(f"=== {code} ({cs.name}) -- {len(products)} active, {len(by_number)} distinct card_number values, {len(dupe_numbers)} numbers with 2+ products ===")

    # Show a few examples of duplicated numbers so we can see if names match
    shown = 0
    for n, rows in sorted(dupe_numbers.items(), key=lambda kv: (kv[0] is None, kv[0]))[:5]:
        names = [r['name'] for r in rows]
        same = len(set(names)) == 1
        print(f"  #{n}: {len(rows)} products, names {'MATCH' if same else 'DIFFER'}: {names}")
        shown += 1
    if not dupe_numbers:
        print("  (no duplicated card_number values)")
    print()
