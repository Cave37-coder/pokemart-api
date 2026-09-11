import sys
sys.path.insert(0, '.')

src = open('/sessions/wonderful-beautiful-lovelace/mnt/pokemart-api/products/completion.py').read()
ns = {'CardSet': object, 'PokemonProduct': object, 'ChecklistEntry': object}
src_no_import = src.replace(
    "from .models import PokemonProduct, CardSet, ChecklistEntry", ""
)
exec(compile(src_no_import, 'completion.py', 'exec'), ns)

is_simple_set = ns['is_simple_set']
compute_set_completion = ns['compute_set_completion']
# Captured now, before Test 4 monkeypatches ns['get_set_card_map'] -- Test 5
# needs the REAL implementation, not a stubbed-out one.
real_get_set_card_map = ns['get_set_card_map']

class FakeEra:
    def __init__(self, name): self.name = name

class FakeSet:
    def __init__(self, total_cards, era_name="Mega Evolution Era"):
        self.total_cards = total_cards
        self.era = FakeEra(era_name)

def entry(card_number, variants, rarity="common"):
    return {"card_number": card_number, "variants": set(variants), "rarity": rarity}

# ── Test 1: ASC-style set. 217 "core rarity" numbered cards (each N + H,
# rarity=common), plus 78 chase-rarity cards (218-295, N only,
# rarity=illustration_rare) that should only ever gate Master
# Set/Full Master -- never Broke Base/Base Set/Special Set Base, no matter
# what card_number they printed at (Michael, 2026-09-11: the ladder is
# rarity-driven, not card_number-range-driven). Keyed the normal
# zero-padded way (no product.number override). User owns every N in the
# core-rarity range only.
card_set = FakeSet(total_cards=217)
card_map = {}
for n in range(1, 218):
    card_map[f"{str(n).zfill(3)}/217"] = entry(n, {"N", "H"}, rarity="common")
for n in range(218, 296):
    card_map[f"{str(n).zfill(3)}/217"] = entry(n, {"N"}, rarity="illustration_rare")
ns['get_set_card_map'] = lambda cs: card_map

checked = {f"{str(n).zfill(3)}/217_N" for n in range(1, 218)}
result = compute_set_completion(card_set, checked)
print("TEST 1: core-rarity N-only owned, no chase cards, no H/RH/balls")
print(result)
assert result['mode'] == 'full'
assert result['tiers']['broke_base']['complete'] is True
assert result['tiers']['base_set']['complete'] is False
assert result['tiers']['special_set_base']['complete'] is False
# Chase-rarity cards (illustration_rare) never touch Broke Base/Base
# Set/Special Set Base's required count -- only the 217 core-rarity cards do.
assert result['tiers']['broke_base']['required'] == 217
assert result['tiers']['base_set']['required'] == 217 * 2  # N + H each
assert result['tiers']['master_set']['owned'] < result['tiers']['master_set']['required']
assert result['tiers']['full_master']['owned'] < result['tiers']['full_master']['required']
print("PASS\n")

# ── Test 2: same set, everything owned.
card_map2 = {}
for n in range(1, 218):
    card_map2[f"{str(n).zfill(3)}/217"] = entry(n, {"N", "H", "RH", "PB", "MB", "LB", "FB", "QB", "UB", "DB"}, rarity="common")
for n in range(218, 296):
    card_map2[f"{str(n).zfill(3)}/217"] = entry(n, {"N"}, rarity="illustration_rare")
ns['get_set_card_map'] = lambda cs: card_map2

checked2 = set()
for n in range(1, 218):
    for v in card_map2[f"{str(n).zfill(3)}/217"]["variants"]:
        checked2.add(f"{str(n).zfill(3)}/217_{v}")
for n in range(218, 296):
    checked2.add(f"{str(n).zfill(3)}/217_N")

result2 = compute_set_completion(card_set, checked2)
print("TEST 2: everything owned (core-rarity full variants + chase cards)")
for tier, data in result2['tiers'].items():
    print(f"  {tier}: {data}")
assert all(t['complete'] for t in result2['tiers'].values())
# Master Set explicitly excludes Pokeball/Masterball variants (Michael,
# 2026-09-11) -- its required count for the core-rarity cards should only
# be N/H/RH (3 each), not the full 10-variant set special_set_base counts.
assert result2['tiers']['master_set']['required'] == 217 * 3 + 78  # N/H/RH * 217 core + N * 78 chase
assert result2['tiers']['special_set_base']['required'] == 217 * 10  # core-rarity only, chase cards excluded
print("PASS\n")

# ── Test 3: simple set (TG-style) -- every card has exactly one variant.
tg_set = FakeSet(total_cards=30, era_name="Sword & Shield Era")
tg_map = {f"{str(n).zfill(3)}/30": entry(n, {"N"}) for n in range(1, 31)}
ns['get_set_card_map'] = lambda cs: tg_map
assert is_simple_set(tg_map) is True

checked3 = {f"{str(n).zfill(3)}/30_N" for n in range(1, 16)}
result3 = compute_set_completion(tg_set, checked3)
print("TEST 3: simple set, half owned")
print(result3)
assert result3['mode'] == 'simple'
assert result3['tiers']['complete_set']['pct'] == 50
print("PASS\n")

# ── Test 4: REGRESSION -- the real TT22 Mewtwo/Haunter collision. Both are
# card_number 56, both variant "TT", distinguished only by their own
# `number` field ("056/172" vs "056/198"). If get_set_card_map grouped by
# card_number instead of display_num, one of these would silently vanish.
tt22_set = FakeSet(total_cards=30, era_name="Trick or Trade")
tt22_map = {
    "056/172": entry(56, {"TT"}),  # Mewtwo
    "056/198": entry(56, {"TT"}),  # Haunter -- same card_number, different card
    "015/192": entry(15, {"TT"}),  # Trevenant
}
ns['get_set_card_map'] = lambda cs: tt22_map
assert is_simple_set(tt22_map) is True
assert len(tt22_map) == 3, "Mewtwo and Haunter must NOT collapse into one entry"

# Only check Mewtwo, not Haunter -- they must score independently.
checked4 = {"056/172_TT"}
result4 = compute_set_completion(tt22_set, checked4)
print("TEST 4: TT22 Mewtwo/Haunter collision -- only Mewtwo checked")
print(result4)
assert result4['mode'] == 'simple'
assert result4['tiers']['complete_set']['owned'] == 1
assert result4['tiers']['complete_set']['required'] == 3
print("PASS\n")

# ── Test 5: REGRESSION -- the real get_set_card_map() id-disambiguation
# path (not mocked out this time). TT22's Nickit (id 404513) and Ariados
# (id 404504) are BOTH physically printed "103/189" -- a genuine number
# clash, not a typo (confirmed with Michael via product photos). This
# exercises the actual two-pass count-then-disambiguate logic inside
# get_set_card_map itself, using a fake PokemonProduct.objects queryset,
# rather than a hand-built card_map like the other tests.
class FakeQuerySet:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, **kwargs):
        return self

    def exclude(self, **kwargs):
        return FakeQuerySet([r for r in self.rows if r["card_number"] is not None])

    def values(self, *fields):
        return [{f: r[f] for f in fields} for r in self.rows]


class FakeManager:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, **kwargs):
        return FakeQuerySet(self.rows)


tt22_rows = [
    {"id": 404513, "card_number": 103, "variant_override": "TT", "number": "103/189", "name": "Nickit", "rarity": "common"},
    {"id": 404504, "card_number": 103, "variant_override": "TT", "number": "103/189", "name": "Ariados", "rarity": "common"},  # clashes with Nickit
    {"id": 404489, "card_number": 56, "variant_override": "TT", "number": "056/172", "name": "Mewtwo", "rarity": "common"},   # no clash
]
class FakePokemonProduct:
    pass

FakePokemonProduct.objects = FakeManager(tt22_rows)
ns['PokemonProduct'] = FakePokemonProduct

tt22_set_real = FakeSet(total_cards=30, era_name="Trick or Trade")
real_card_map = real_get_set_card_map(tt22_set_real)
print("TEST 5: real get_set_card_map() id-disambiguation (Nickit/Ariados)")
print(real_card_map)
assert set(real_card_map.keys()) == {"103/189-404513", "103/189-404504", "056/172"}, real_card_map
assert real_card_map["103/189-404513"]["card_number"] == 103
assert real_card_map["103/189-404504"]["card_number"] == 103
assert real_card_map["056/172"]["card_number"] == 56
print("PASS\n")

print("ALL TESTS PASSED")
