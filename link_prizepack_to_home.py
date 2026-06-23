"""
Links every PRIZEPACK product to its "home set" printing:
  - Copies image_url/image_small_url from the home printing (variant-aware:
    prefers a home product with the same variant_override, e.g. H matches H)
  - Tags prize_pack_series with the comma-separated series numbers from the
    official Pokemon.com checklists
  - Does NOT touch price, stock, or any other field — pricing stays
    completely independent, sourced from TCGCSV as always

Dry-run by default. Review the printed plan, then set DRY_RUN = False and
rerun to apply.

Run from C:\\Users\\texca\\pokemart-api with DATABASE_URL uncommented:
    python manage.py shell -c "exec(open('link_prizepack_to_home.py').read())"
"""
import json
import re
from collections import defaultdict
from difflib import SequenceMatcher
from products.models import PokemonProduct, CardSet

DRY_RUN = False  # confirmed via dry run — applying now

# Confirmed by hand for cases the automated tiers couldn't resolve cleanly
MANUAL_OVERRIDE_BY_ID = {
    447229: 'BRS',   # Boss's Orders [Cyrus] - 132/172 -> Brilliant Stars (172 cards)
    447206: 'SHF',   # Dusknoir - 020/064 -> Shrouded Fable (64 cards)
    405656: 'SHF',   # Dusknoir - 020/064 (other variant row) -> Shrouded Fable
    405172: 'CPA',   # Alcremie VMAX -> Celebrations (per Series 1 official list)
}

# Low confidence or home product genuinely missing from the DB — skip rather
# than risk a wrong match. Revisit manually later if desired.
SKIP_IDS = {
    405553,  # Pecharunt ex (card_number=39) — not found in any of the 9 official lists at this number
    405251,  # Altaria - 49/73 — denominator doesn't cleanly resolve to a known set
    447104,  # Glaceon VSTAR (SWSH197) — expected home set SWSH has no matching product in DB at all
}

with open('prize_pack_lookup.json', encoding='utf-8') as f:
    lookup = json.load(f)
num_index = defaultdict(list)
for key, series_list in lookup.items():
    code, num = key.rsplit('_', 1)
    num_index[num].append((code, series_list))

set_total_cards = {cs.code: cs.total_cards for cs in CardSet.objects.all()}
DENOM_IN_NAME_RE = re.compile(r'(\d{1,4})/(\d{1,4})')

pp = CardSet.objects.get(id=143)
products = list(PokemonProduct.objects.filter(card_set=pp))
total = len(products)
print(f"Total PRIZEPACK products to check: {total}")

print("Prefetching all non-PRIZEPACK products into memory...")
all_other = (PokemonProduct.objects.exclude(card_set=pp)
             .exclude(card_set__isnull=True)
             .select_related('card_set')
             .values('id', 'card_set__code', 'card_number', 'name', 'variant_override',
                      'image_url', 'image_small_url'))
by_set_num = defaultdict(list)  # (code, num) -> list of row dicts
for row in all_other:
    by_set_num[(row['card_set__code'], row['card_number'])].append(row)
print(f"Prefetched {len(all_other)} products.\n")


def official_candidates_for(card_number):
    return [code for code, _ in num_index.get(str(card_number).zfill(3), [])]


def find_home_by_denominator(card_number, denominator):
    matches = [code for code, tc in set_total_cards.items() if tc == denominator and code != 'PRIZEPACK']
    return [code for code in matches if by_set_num.get((code, card_number))]


def resolve_home_code(p):
    """Returns the confirmed home set_code for product p, or None."""
    if p.id in MANUAL_OVERRIDE_BY_ID:
        return MANUAL_OVERRIDE_BY_ID[p.id]
    if p.id in SKIP_IDS or p.card_number is None:
        return None

    official = official_candidates_for(p.card_number)
    denom = None
    if p.number and '/' in p.number:
        try:
            denom = int(p.number.split('/')[1])
        except ValueError:
            denom = None
    if denom is None:
        m = DENOM_IN_NAME_RE.search(p.name)
        if m:
            denom = int(m.group(2))

    if denom is not None:
        confirmed = find_home_by_denominator(p.card_number, denom)
        if len(confirmed) == 1 and (not official or confirmed[0] in official):
            return confirmed[0]

    if official and denom is not None:
        denom_filtered = [c for c in official if set_total_cards.get(c) == denom]
        if len(denom_filtered) == 1:
            return denom_filtered[0]

    if official and len(official) == 1:
        if by_set_num.get((official[0], p.card_number)):
            return official[0]

    if official:
        best_code, best_score = None, 0.0
        for code in official:
            for row in by_set_num.get((code, p.card_number), []):
                score = SequenceMatcher(None, p.name.lower(), row['name'].lower()).ratio()
                if score > best_score:
                    best_score, best_code = score, code
        if best_code and best_score >= 0.5:
            return best_code

    return None


planned = []  # (product, home_code, home_row, series_list)
skipped_no_home_row = []
skipped_no_match = []

for p in products:
    home_code = resolve_home_code(p)
    if not home_code:
        skipped_no_match.append(p)
        continue

    candidates = by_set_num.get((home_code, p.card_number), [])
    if not candidates:
        skipped_no_home_row.append((p, home_code))
        continue

    # Variant-aware: prefer a home row with the same variant_override
    home_row = next((r for r in candidates if r['variant_override'] == p.variant_override), candidates[0])

    series_list = lookup.get(f"{home_code}_{str(p.card_number).zfill(3)}", [])
    planned.append((p, home_code, home_row, series_list))

print(f"Planned updates: {len(planned)}")
print(f"Skipped — matched a home set but no actual product row there: {len(skipped_no_home_row)}")
print(f"Skipped — no match / manual skip / no card_number: {len(skipped_no_match)}")

print("\n--- Sample of 15 planned updates ---")
for p, code, row, series_list in planned[:15]:
    print(f"  id={p.id} {p.name!r}")
    print(f"    -> home {code} card_number={p.card_number} (home id={row['id']}, variant={row['variant_override']!r})")
    print(f"    -> new image_url: {row['image_url']!r}")
    print(f"    -> prize_pack_series: {','.join(str(s) for s in series_list)}")

if DRY_RUN:
    print(f"\nDRY RUN — nothing changed. {len(planned)} rows would be updated. Set DRY_RUN = False and rerun to apply.")
else:
    to_update = []
    for p, code, row, series_list in planned:
        p.image_url = row['image_url']
        p.image_small_url = row['image_small_url']
        p.prize_pack_series = ','.join(str(s) for s in series_list)
        to_update.append(p)
    PokemonProduct.objects.bulk_update(to_update, ['image_url', 'image_small_url', 'prize_pack_series'], batch_size=200)
    print(f"\nApplied updates to {len(to_update)} products.")
