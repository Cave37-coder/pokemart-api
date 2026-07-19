"""
sync_missing_variants.py

Run AFTER cleanup_wrong_variants.py. Finds every (product_id, variant)
combination TCGCSV lists (via the bible) for PRE, ASC, WHT, BLK that has
NO corresponding row in the DB at all, and creates it with the correct
current price straight from TCGCSV's pokebulk_zar field -- this is the
actual fix for the pricing bug (cards selling at R2.50 when the real
TCGCSV price is R6.50): once this and the cleanup script have both run,
every row in the DB will be exactly the set of (product_id, variant)
pairs TCGCSV actually lists, each with TCGCSV's real current price.

New rows are created with stock=0 (no physical count yet -- you'll do a
fresh stock count after this runs, per your plan).

Usage:
    python manage.py shell -c "exec(open('sync_missing_variants.py').read())"

DRY RUN by default -- shows what would be created, changes nothing.
Set APPLY = True to actually create rows.
"""

import csv
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from products.models import PokemonProduct, CardSet

APPLY = False  # flip to True once the dry-run output looks right

TARGET_SETS = ['PRE', 'ASC', 'WHT', 'BLK']
BIBLE_CSV_PATH = 'pokebulk_bible_v7.csv'  # adjust if it's elsewhere

# Sort order confirmed earlier this session (fix_variant_sort_order.py) --
# reused here so newly created rows get the correct sort value immediately.
VARIANT_ORDER = [
    "N", "H", "RH",
    "PB", "MB", "LB", "FB", "QB", "UB", "DB",
    "TR", "SE", "PBP", "MBP", "CC", "TT",
]
VARIANT_SORT_MAP = {code: i for i, code in enumerate(VARIANT_ORDER)}

RARITY_MAP = {
    # Confirmed against every rarity value actually present in the bible
    # for PRE/ASC/WHT/BLK (checked via Counter before building this).
    'common': 'common', 'uncommon': 'uncommon', 'rare': 'rare',
    'holo rare': 'holo_rare', 'rare holo': 'holo_rare',
    'ultra rare': 'ultra_rare', 'double rare': 'ultra_rare',
    'illustration rare': 'illustration_rare',
    'special illustration rare': 'special_illustration_rare',
    'hyper rare': 'hyper_rare', 'secret rare': 'secret_rare',
    'ace spec rare': 'ace_spec',
    'mega attack rare': 'mega_attack_rare',
    'mega hyper rare': 'mega_hyper_rare',
    # Not a real distinct rarity tier -- code cards just use whatever the
    # model default/closest bucket is; doesn't affect pricing logic.
    'code card': 'common',
    # No exact model equivalent for this SV-era tier -- best approximation,
    # flag and verify manually if this shows up in the dry-run output.
    'black white rare': 'secret_rare',
}

print(f"Mode: {'APPLY (creating rows)' if APPLY else 'DRY RUN (no changes will be made)'}")
print()

with open(BIBLE_CSV_PATH, encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    bible_rows = [r for r in reader if r.get('set_code', '').strip() in TARGET_SETS and r.get('is_card', '').strip().lower() == 'true']

print(f"Bible card rows for {TARGET_SETS}: {len(bible_rows)}")

# What already exists in the DB
db_products = PokemonProduct.objects.filter(card_set__code__in=TARGET_SETS).select_related('card_set')
existing = set()
for p in db_products:
    if p.tcgcsv_product_id:
        existing.add((p.card_set.code, str(p.tcgcsv_product_id), (p.variant_override or 'N').strip()))

print(f"Existing DB (set, product_id, variant) combos: {len(existing)}")
print()

card_sets_cache = {sc: CardSet.objects.filter(code=sc).first() for sc in TARGET_SETS}
missing_cs = [sc for sc, cs in card_sets_cache.items() if cs is None]
if missing_cs:
    print(f"WARNING: CardSet not found in DB for: {missing_cs} -- rows for these will be skipped.")
    print()

to_create = []
unmapped_rarity = []

for row in bible_rows:
    sc = row['set_code'].strip()
    pid = row['product_id'].strip()
    variant = row['variant_code'].strip()
    key = (sc, pid, variant)

    if key in existing:
        continue
    if card_sets_cache.get(sc) is None:
        continue

    to_create.append(row)

print(f"Missing rows to create: {len(to_create)}")
print()

from collections import Counter
create_by_set = Counter(r['set_code'] for r in to_create)
for sc in TARGET_SETS:
    print(f"  {sc}: {create_by_set.get(sc, 0)} rows to create")
print()

if to_create:
    print("Sample (first 20):")
    for row in to_create[:20]:
        price = row.get('pokebulk_zar', '').strip()
        print(f"  [{row['set_code']}] {row['name']} -- variant={row['variant_code']} price=R{price} (product_id={row['product_id']})")

if APPLY and to_create:
    print("\nCreating...")
    created = 0
    errors = []
    for row in to_create:
        sc = row['set_code'].strip()
        cs = card_sets_cache[sc]
        variant = row['variant_code'].strip()
        rarity_raw = row.get('rarity', '').strip().lower()
        rarity = RARITY_MAP.get(rarity_raw)
        if not rarity:
            unmapped_rarity.append((row['name'], rarity_raw))
            rarity = 'common'  # fallback so creation doesn't hard-fail; fix manually after if flagged below

        try:
            price = Decimal(row.get('pokebulk_zar', '0').strip() or '0')
        except InvalidOperation:
            price = Decimal('0')

        try:
            card_number = int(float(row.get('card_number', '0') or 0))
        except (ValueError, TypeError):
            card_number = None

        try:
            pokedex_number = int(float(row.get('final_pokedex', '') or 0)) or None
        except (ValueError, TypeError):
            pokedex_number = None

        try:
            PokemonProduct.objects.create(
                # pb_id and sku are intentionally NOT set here -- both are
                # editable=False and auto-generated by the model's own
                # save() override (generate_pb_id() / generate_sku()) as
                # long as card_set, pokedex_number, and card_number are all
                # present. Constructing pb_id manually risks a format that
                # doesn't match the model's real convention.
                tcgcsv_product_id=int(row['product_id']),
                name=row.get('name', ''),
                card_set=cs,
                rarity=rarity,
                pokedex_number=pokedex_number,
                card_number=card_number,
                number=row.get('number', '').strip(),
                variant_override=variant,
                variant_sort=VARIANT_SORT_MAP.get(variant, 99),
                price=price,
                stock=0,
                image_url=row.get('final_image_url', '').strip(),
                image_small_url=row.get('final_image_url', '').strip(),
                artist=row.get('final_artist', row.get('artist', '')).strip(),
                regulation_mark=row.get('final_regulation_mark', '').strip(),
            )
            created += 1
        except Exception as e:
            errors.append((row['name'], row['product_id'], variant, str(e)))

        if created % 25 == 0 and created:
            print(f"  created {created}/{len(to_create)}...")

    print(f"\nDone. Created {created} row(s).")
    if errors:
        print(f"\n{len(errors)} row(s) FAILED to create:")
        for name, pid, variant, err in errors[:20]:
            print(f"  {name} (product_id={pid}, variant={variant}) -- {err}")
elif to_create:
    print("\nDry run only -- no rows created. Set APPLY = True and re-run to apply.")
else:
    print("\nNothing to create.")

if unmapped_rarity:
    print(f"\n{len(unmapped_rarity)} row(s) had an unrecognized rarity value (defaulted to 'common' -- fix manually):")
    for name, raw in unmapped_rarity[:20]:
        print(f"  {name} -- rarity={raw!r}")
