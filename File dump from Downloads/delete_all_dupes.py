from django.db import transaction
from products.models import CardSet, PokemonProduct

# Delete the empty duplicate codes (0 cards)
TO_DELETE = [
    # B1
    'PR-NP', 'PR',
    # B3
    'CoL', 'PR-DP',
    # B6
    'SM03', 'SM12', 'SM04', 'DEP', 'SM06', 'SM02', 'SMA',
    'SM8', 'SHL', 'SM01', 'SM9', 'SM05', 'SM10', 'SM11',
    # B7
    'SWSH05',
    # B8
    'OBF', 'PAL', 'PAF', 'PAR', 'SVI',
]

# Also delete codes WITH cards where duplicate has more cards
# PR-NB(63) vs PR-NP(70) -> delete PR-NB (fewer)
# PR(106) vs PR-WB(60) -> delete PR-WB (fewer)
# CL(190) vs CoL(0) -> delete CoL (already above)
# PR-DPP(111) vs PR-DP(58) -> delete PR-DP (fewer)
# SMA(92) vs HIFSV(94) -> delete SMA (fewer)
# DET(32) vs DEP(18) -> delete DEP (fewer, already above)
# BST(304) vs SWSH05(0) -> delete SWSH05 (already above)
# SV3(406) vs OBF(0) -> delete OBF (already above)

# Fix: keep the one with MORE cards
KEEP_WINNER = {
    'PR-NB': ('PR-NP', 70),   # PR-NP has more, delete PR-NB
    'PR-WB': ('PR', 106),      # PR has more, delete PR-WB... wait PR-WB is our code
}

# Actually just delete the ones with 0 cards first, then handle ties
with transaction.atomic():
    deleted_count = 0
    for code in TO_DELETE:
        try:
            cards = PokemonProduct.objects.filter(card_set__code=code).count()
            if cards > 0:
                print(f"SKIP {code} — has {cards} cards")
                continue
            PokemonProduct.objects.filter(card_set__code=code).delete()
            CardSet.objects.filter(code=code).delete()
            print(f"Deleted {code}")
            deleted_count += 1
        except Exception as e:
            print(f"Error {code}: {e}")

    # Handle the ones where both have cards — delete the one with fewer
    # PR-NB(63) vs PR-NP(70): keep PR-NP, delete PR-NB
    for code, (keep, keep_count) in [
        ('PR-NB', ('PR-NP', 70)),
        ('PR-WB', ('PR-WB', 60)),  # keep PR-WB our proper code, delete PR
        ('PR-DPP', ('PR-DPP', 111)),  # keep PR-DPP, delete PR-DP
        ('SMA', ('HIFSV', 94)),  # keep HIFSV, delete SMA
        ('DET', ('DET', 32)),  # keep DET, delete DEP (already gone)
    ]:
        pass  # handled above

    # Delete PR (old WotC promo code with 106 cards) — keep PR-WB
    try:
        count = PokemonProduct.objects.filter(card_set__code='PR').count()
        if count > 0:
            PokemonProduct.objects.filter(card_set__code='PR').delete()
        CardSet.objects.filter(code='PR').delete()
        print(f"Deleted PR ({count} products)")
        deleted_count += 1
    except Exception as e:
        print(f"Error PR: {e}")

    # Delete PR-NB (63 cards) — keep PR-NP (70 cards)
    try:
        count = PokemonProduct.objects.filter(card_set__code='PR-NB').count()
        PokemonProduct.objects.filter(card_set__code='PR-NB').delete()
        CardSet.objects.filter(code='PR-NB').delete()
        print(f"Deleted PR-NB ({count} products)")
        deleted_count += 1
    except Exception as e:
        print(f"Error PR-NB: {e}")

    # Delete PR-DP (58 cards) — keep PR-DPP (111 cards)
    try:
        count = PokemonProduct.objects.filter(card_set__code='PR-DP').count()
        PokemonProduct.objects.filter(card_set__code='PR-DP').delete()
        CardSet.objects.filter(code='PR-DP').delete()
        print(f"Deleted PR-DP ({count} products)")
        deleted_count += 1
    except Exception as e:
        print(f"Error PR-DP: {e}")

    # Delete SMA (92 cards) — keep HIFSV (94 cards)
    try:
        count = PokemonProduct.objects.filter(card_set__code='SMA').count()
        PokemonProduct.objects.filter(card_set__code='SMA').delete()
        CardSet.objects.filter(code='SMA').delete()
        print(f"Deleted SMA ({count} products)")
        deleted_count += 1
    except Exception as e:
        print(f"Error SMA: {e}")

    # Delete DET (32) — keep DEP (18)... actually DET has more, keep DET
    try:
        count = PokemonProduct.objects.filter(card_set__code='DEP').count()
        PokemonProduct.objects.filter(card_set__code='DEP').delete()
        CardSet.objects.filter(code='DEP').delete()
        print(f"Deleted DEP ({count} products)")
        deleted_count += 1
    except Exception as e:
        print(f"Error DEP: {e}")

    # Delete CL (190) vs CoL(0) — CoL already deleted, but CL has old code
    # Keep CL since it has cards, rename? Actually keep CL
    # Delete BST (304 TG cards) vs SWSH05 (0) — SWSH05 already deleted above

print(f"\nTotal deleted: {deleted_count} sets")
print("Running dupe check again...")
from collections import defaultdict
by_era_name = defaultdict(list)
for cs in CardSet.objects.select_related('era').all():
    key = (cs.era.code if cs.era else 'NONE', cs.name)
    by_era_name[key].append(cs.code)
remaining = [(era, name, codes) for (era, name), codes in by_era_name.items() if len(codes) > 1]
if remaining:
    print(f"Remaining dupes: {len(remaining)}")
    for era, name, codes in remaining:
        print(f"  {era} {name}: {codes}")
else:
    print("No more duplicates!")
