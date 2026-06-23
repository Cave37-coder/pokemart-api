"""
Read-only diagnostic. Does NOT change anything in the database.

For every product currently under PRIZEPACK, tries to find its "home set"
printing (the original card this is a reprint of) using the official
series lookup table (prize_pack_lookup.json, built from all 9 official
Pokemon.com checklists).

Match key is (card_number) -> candidate home set codes. If there's exactly
one candidate, AND a real product exists in the DB at that (set_code,
card_number), that's a clean match. If there are multiple candidates, we
report it as ambiguous rather than guessing. If there are zero candidates,
it's unmatched (could be a Series 1-3 bare-numbered energy, a data gap in
the official lists, or a genuinely new/unlisted card).

Run from C:\\Users\\texca\\pokemart-api with DATABASE_URL uncommented:
    python manage.py shell -c "exec(open('diagnose_prizepack_matching.py').read())"
"""
import json
from collections import defaultdict
from products.models import PokemonProduct, CardSet

with open('prize_pack_lookup.json', encoding='utf-8') as f:
    lookup = json.load(f)  # "CODE_NUM" -> [series list]

# Build a num -> [(code, series_list), ...] reverse index for disambiguation
num_index = defaultdict(list)
for key, series_list in lookup.items():
    code, num = key.rsplit('_', 1)
    num_index[num].append((code, series_list))

pp = CardSet.objects.get(id=143)  # PRIZEPACK
products = PokemonProduct.objects.filter(card_set=pp).select_related('card_set')
total = products.count()
print(f"Total PRIZEPACK products to check: {total}\n")

clean_matches = 0
ambiguous = []
unmatched = []
home_product_missing = []

for p in products.iterator():
    if p.card_number is None:
        unmatched.append(p)
        continue

    num_str = str(p.card_number).zfill(3)
    candidates = num_index.get(num_str, [])

    if len(candidates) == 0:
        unmatched.append(p)
        continue

    if len(candidates) == 1:
        code, series_list = candidates[0]
        # Does the actual home-set product exist in our DB?
        home = PokemonProduct.objects.filter(
            card_set__code=code, card_number=p.card_number
        ).exclude(card_set=pp).first()
        if home:
            clean_matches += 1
        else:
            home_product_missing.append((p, code, series_list))
        continue

    # Multiple candidates — ambiguous, needs name-based disambiguation later
    ambiguous.append((p, candidates))

print(f"Clean matches (exactly 1 candidate set, home product exists in DB): {clean_matches}")
print(f"Ambiguous (multiple candidate home sets for this card number): {len(ambiguous)}")
print(f"Candidate found but home product missing from DB: {len(home_product_missing)}")
print(f"No candidate at all (likely Series 1-3 bare energy, or not in any official list): {len(unmatched)}")

if ambiguous:
    print(f"\n--- Ambiguous matches (first 20 of {len(ambiguous)}) ---")
    for p, candidates in ambiguous[:20]:
        codes = [c for c, _ in candidates]
        print(f"  id={p.id} card_number={p.card_number} name={p.name!r} candidates={codes}")

if home_product_missing:
    print(f"\n--- Candidate matched but no home product in DB (first 20 of {len(home_product_missing)}) ---")
    for p, code, series_list in home_product_missing[:20]:
        print(f"  id={p.id} card_number={p.card_number} name={p.name!r} expected_set={code}")

if unmatched:
    print(f"\n--- Unmatched (first 20 of {len(unmatched)}) ---")
    for p in unmatched[:20]:
        print(f"  id={p.id} card_number={p.card_number} name={p.name!r}")
