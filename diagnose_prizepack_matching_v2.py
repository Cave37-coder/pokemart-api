"""
Read-only diagnostic. Does NOT change anything in the database.

3-tier matching strategy to find each PRIZEPACK product's "home set" printing:
  Tier 1: parse denominator from the structured `number` field (e.g. "020/064")
  Tier 2: parse denominator from the `name` string itself (e.g. "- 020/064")
  Tier 3: no denominator available — use the official series-list candidates
          for this card_number, disambiguated by fuzzy name match against
          actual products in each candidate set.

A denominator match means: card_number matches AND CardSet.total_cards
matches AND a real product exists in that set at that card_number.

Run from C:\\Users\\texca\\pokemart-api with DATABASE_URL uncommented:
    python manage.py shell -c "exec(open('diagnose_prizepack_matching_v2.py').read())"
"""
import json
import re
from collections import defaultdict
from difflib import SequenceMatcher
from products.models import PokemonProduct, CardSet

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

print("Prefetching all non-PRIZEPACK products into memory (one big query)...")
# Build: (set_code, card_number) -> list of (name,) for every other set's products.
# This is the ONE query that replaces thousands of per-item lookups.
all_other = (PokemonProduct.objects.exclude(card_set=pp)
             .exclude(card_set__isnull=True)
             .select_related('card_set')
             .values('card_set__code', 'card_number', 'name'))
by_set_num = defaultdict(list)
for row in all_other:
    by_set_num[(row['card_set__code'], row['card_number'])].append(row['name'])
print(f"Prefetched {len(all_other)} products into {len(by_set_num)} (set, number) buckets.\n")


def find_home_by_denominator(card_number, denominator):
    matches = [code for code, tc in set_total_cards.items() if tc == denominator and code != 'PRIZEPACK']
    confirmed = [code for code in matches if by_set_num.get((code, card_number))]
    return confirmed


tier1, tier2, tier3, no_match = 0, 0, 0, []
tier1_suspicious, tier2_suspicious = 0, 0
no_match_details = []


def official_candidates_for(card_number):
    return [code for code, _ in num_index.get(str(card_number).zfill(3), [])]


for i, p in enumerate(products, 1):
    if i % 100 == 0:
        print(f"Progress: {i}/{total}  (tier1={tier1} tier2={tier2} tier3={tier3} no_match={len(no_match)})")

    if p.card_number is None:
        no_match.append(p)
        no_match_details.append((p, 'no card_number'))
        continue

    official = official_candidates_for(p.card_number)
    matched = False

    # Tier 1: structured number field denominator
    if p.number and '/' in p.number:
        try:
            denom = int(p.number.split('/')[1])
            confirmed = find_home_by_denominator(p.card_number, denom)
            if len(confirmed) == 1:
                code = confirmed[0]
                # Sanity cross-check: does the official list agree, if it has an opinion at all?
                if not official or code in official:
                    tier1 += 1
                    matched = True
                else:
                    tier1_suspicious += 1
                    # disagreement with official list — don't trust blindly, fall through
        except ValueError:
            pass

    # Tier 2: denominator hiding in the name string
    if not matched:
        m = DENOM_IN_NAME_RE.search(p.name)
        if m:
            denom = int(m.group(2))
            confirmed = find_home_by_denominator(p.card_number, denom)
            if len(confirmed) == 1:
                code = confirmed[0]
                if not official or code in official:
                    tier2 += 1
                    matched = True
                else:
                    tier2_suspicious += 1

    # Tier 3: official-list candidates — denominator first, then lone-candidate
    # acceptance, then fuzzy name match as last resort
    if not matched:
        if not official:
            no_match.append(p)
            no_match_details.append((p, 'no candidates in official list (and tier1/2 did not resolve)'))
            continue

        # 3a: if we have a denominator (from number field or name), use it to
        # narrow the official candidates directly — most reliable signal available
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
            denom_filtered = [c for c in official if set_total_cards.get(c) == denom]
            if len(denom_filtered) == 1:
                tier3 += 1
                matched = True

        # 3b: only one official candidate at all — no ambiguity to resolve
        if not matched and len(official) == 1:
            if by_set_num.get((official[0], p.card_number)):
                tier3 += 1
                matched = True

        # 3c: fuzzy name match as last resort
        if not matched:
            best_code, best_score = None, 0.0
            for code in official:
                for home_name in by_set_num.get((code, p.card_number), []):
                    score = SequenceMatcher(None, p.name.lower(), home_name.lower()).ratio()
                    if score > best_score:
                        best_score, best_code = score, code

            if best_code and best_score >= 0.5:
                tier3 += 1
                matched = True
            else:
                no_match.append(p)
                no_match_details.append((p, f'tier3 best_score={best_score:.2f} candidates={official}'))

print(f"Tier 1 (number field denominator):  {tier1}")
print(f"Tier 2 (name string denominator):   {tier2}")
print(f"Tier 3 (fuzzy name match, incl. tier1/2 fallthroughs): {tier3}")
print(f"Tier 1 disagreed with official list (fell through):  {tier1_suspicious}")
print(f"Tier 2 disagreed with official list (fell through):  {tier2_suspicious}")
print(f"No match:                           {len(no_match)}")
print(f"TOTAL matched: {tier1 + tier2 + tier3} / {total}")

print(f"\n--- No-match details (first 40 of {len(no_match)}) ---")
for p, reason in no_match_details[:40]:
    print(f"  id={p.id} card_number={p.card_number} name={p.name!r}\n      reason: {reason}")
