import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import PokemonProduct, CardSet

# Michael asked for an exact data breakdown of the Trainer Gallery / Galarian
# Gallery products, after a screenshot-reading mistake earlier in this
# session. The Bible (pokebulk_bible_v7_r2_with_pokedex.csv) gives the
# authoritative TG01-30 / GG01-70 name+number list, already cross-checked
# against Serebii directly. This script dumps the ACTUAL stored DB state
# (id, name, card_number, stock) for the same 5 CardSets, sorted by
# card_number, so it can be diffed against the Bible with zero ambiguity --
# no screenshot reading, no guessing.

CODES = ['BRSTG', 'ASRTG', 'LORTG', 'SITTG', 'CRZGG']

for code in CODES:
    try:
        cs = CardSet.objects.get(code=code)
    except CardSet.DoesNotExist:
        print(f"=== {code}: no such CardSet ===")
        continue
    products = list(
        PokemonProduct.objects.filter(card_set=cs, is_active=True)
        .order_by('card_number')
        .values('id', 'name', 'card_number', 'stock', 'pos_stock')
    )
    print(f"=== {code} ({cs.name}) -- {len(products)} active products ===")
    for p in products:
        print(f"  id={p['id']:<8} card_number={str(p['card_number']):<6} stock={p['stock']:<4} pos_stock={p['pos_stock']:<4} name={p['name']!r}")
    print()
