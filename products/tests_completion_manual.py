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

# ── Test 1: ASC/POR-style set. 217 numbered cards (card_number <= 217,
# each N + H, rarity=common -- rarity doesn't matter for the numbered
# range, confirmed live: Common through EX all live inside it), plus 78
# unnumbered cards (card_number 218-295) split into two chase buckets --
# 218-250 tagged illustration_rare (Master Set requires these too, per
# Michael, 2026-09-11: "Master Set ... all illustration Rares") and
# 251-295 tagged ultra_rare (alt-art/secret reprints living past the
# numbered range -- these only ever count for Full Master, NOT Master
# Set: Michael, 2026-09-11, after live-testing: "cards under 088 are
# numbered, the rest ... are unnumbered" -- numbered/unnumbered is the
# real gate, rarity only narrows what Master Set additionally pulls in
# from the unnumbered pool). User owns every N in the numbered range only.
card_set = FakeSet(total_cards=217)
card_map = {}
for n in range(1, 218):
    card_map[f"{str(n).zfill(3)}/217"] = entry(n, {"N", "H"}, rarity="common")
for n in range(218, 251):
    card_map[f"{str(n).zfill(3)}/217"] = entry(n, {"N"}, rarity="illustration_rare")
for n in range(251, 296):
    card_map[f"{str(n).zfill(3)}/217"] = entry(n, {"N"}, rarity="ultra_rare")
ns['get_set_card_map'] = lambda cs: card_map

checked = {f"{str(n).zfill(3)}/217_N" for n in range(1, 218)}
result = compute_set_completion(card_set, checked)
print("TEST 1: numbered N-only owned, no unnumbered cards, no H/RH/balls")
print(result)
assert result['mode'] == 'full'
assert result['tiers']['broke_base']['complete'] is True
assert result['tiers']['base_set']['complete'] is False
assert result['tiers']['special_set_base']['complete'] is False
# Unnumbered cards (whatever their rarity) never touch Broke Base/Base
# Set/Special Set Base's required count -- only the 217 numbered cards do.
assert result['tiers']['broke_base']['required'] == 217
assert result['tiers']['base_set']['required'] == 217 * 2  # N + H each
# Master Set pulls in the 33 illustration_rare unnumbered cards but NOT
# the 45 ultra_rare ones -- required = 217 numbered (N+H each, no balls)
# + 33 illustration_rare (N each).
assert result['tiers']['master_set']['required'] == 217 * 2 + 33
assert result['tiers']['master_set']['owned'] < result['tiers']['master_set']['required']
# Full Master requires literally everything -- all 295 cards.
assert result['tiers']['full_master']['required'] == 217 * 2 + 78
assert result['tiers']['full_master']['owned'] < result['tiers']['full_master']['required']
print("PASS\n")

# ── Test 2: same set, everything owned.
card_map2 = {}
for n in range(1, 218):
    card_map2[f"{str(n).zfill(3)}/217"] = entry(n, {"N", "H", "RH", "PB", "MB", "LB", "FB", "QB", "UB", "DB"}, rarity="common")
for n in range(218, 251):
    card_map2[f"{str(n).zfill(3)}/217"] = entry(n, {"N"}, rarity="illustration_rare")
for n in range(251, 296):
    card_map2[f"{str(n).zfill(3)}/217"] = entry(n, {"N"}, rarity="ultra_rare")
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
# 2026-09-11) -- its required count for the numbered cards should only be
# N/H/RH (3 each), not the full 10-variant special_set_base count, PLUS
# only the 33 illustration_rare unnumbered cards (not all 78 unnumbered).
assert result2['tiers']['master_set']['required'] == 217 * 3 + 33
assert result2['tiers']['special_set_base']['required'] == 217 * 10  # numbered only, unnumbered cards excluded
assert result2['tiers']['full_master']['required'] == 217 * 10 + 78  # everything, every rarity
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

# ── Test 6: REGRESSION -- era-aware Master Set chase rarities (Michael,
# 2026-09-11, after "deep dive the net" research). Illustration Rare is
# SV/MEG-only vocabulary; pre-SV eras (WotC through SWSH) tag their own
# unnumbered past-the-print-run chase cards "secret_rare" instead
# (confirmed live on XY-era Evolutions: "Surfing Pikachu" 111/108,
# rarity secret_rare). Michael's custom MEG-era sets also mint their own
# top-tier "mega_hyper_rare"/"mega_attack_rare" cards beyond Illustration
# Rare (e.g. Mega Charizard Y ex 294/217 in Ascended Heroes). All three
# must now count toward Master Set, same as illustration_rare/
# special_illustration_rare always did. A plain "ultra_rare" unnumbered
# card (re-tagged alt-art reprint, not a named chase tier) must NOT.
xy_set = FakeSet(total_cards=108, era_name="XY Era")
xy_map = {}
for n in range(1, 109):
    xy_map[f"{str(n).zfill(3)}/108"] = entry(n, {"N", "H"}, rarity="common")
xy_map["109/108"] = entry(109, {"N"}, rarity="secret_rare")     # like Surfing Pikachu
xy_map["110/108"] = entry(110, {"N"}, rarity="ultra_rare")      # re-tagged alt-art, NOT a named chase tier
ns['get_set_card_map'] = lambda cs: xy_map

checked6 = {f"{str(n).zfill(3)}/108_N" for n in range(1, 109)}
checked6 |= {f"{str(n).zfill(3)}/108_H" for n in range(1, 109)}
checked6.add("109/108_N")
result6 = compute_set_completion(xy_set, checked6)
print("TEST 6a: XY-era secret_rare counts toward Master Set, ultra_rare doesn't")
print(result6['tiers']['master_set'])
assert result6['tiers']['master_set']['required'] == 108 * 2 + 1  # numbered N+H each, + the one secret_rare
assert result6['tiers']['master_set']['complete'] is True  # owns all numbered N + the secret_rare
assert result6['tiers']['full_master']['required'] == 108 * 2 + 2  # both unnumbered cards count here
print("PASS\n")

meg_set = FakeSet(total_cards=217, era_name="Mega Evolution Era")
meg_map = {}
for n in range(1, 218):
    meg_map[f"{str(n).zfill(3)}/217"] = entry(n, {"N", "H"}, rarity="common")
meg_map["294/217"] = entry(294, {"H"}, rarity="mega_hyper_rare")   # like Mega Charizard Y ex
meg_map["265/217"] = entry(265, {"H"}, rarity="mega_attack_rare")  # like Mega Froslass ex
ns['get_set_card_map'] = lambda cs: meg_map

checked6b = {f"{str(n).zfill(3)}/217_N" for n in range(1, 218)}
checked6b |= {f"{str(n).zfill(3)}/217_H" for n in range(1, 218)}
checked6b.add("294/217_H")
checked6b.add("265/217_H")
result6b = compute_set_completion(meg_set, checked6b)
print("TEST 6b: MEG-era mega_hyper_rare/mega_attack_rare count toward Master Set")
print(result6b['tiers']['master_set'])
assert result6b['tiers']['master_set']['required'] == 217 * 2 + 2
assert result6b['tiers']['master_set']['complete'] is True
print("PASS\n")

# ── Test 7: REGRESSION -- the real UFUC bug (2026-09-11). Letter-numbered
# cards (Unown Collection: "A/28".."Z/28", "!/28", "?/28") have no integer
# card_number at all -- get_set_card_map() used to .exclude(card_number__
# isnull=True), which silently dropped them entirely, leaving UFUC's
# get_set_card_map() empty and every tier showing required=0. Fixed by
# only skipping a row when it has NEITHER a usable `number` string NOR a
# card_number. This is a simple set (one print per Unown), single H
# variant each.
ufuc_set = FakeSet(total_cards=28, era_name="EX Era")
ufuc_map = {}
for letter in ["!", "?"] + [chr(c) for c in range(ord("A"), ord("Z") + 1)]:
    num = f"{letter}/28"
    ufuc_map[num] = {"card_number": None, "variants": {"H"}, "rarity": "holo_rare"}
ns['get_set_card_map'] = lambda cs: ufuc_map
assert is_simple_set(ufuc_map) is True

checked7 = {f"{letter}/28_H" for letter in ["!", "?"] + [chr(c) for c in range(ord("A"), ord("N") + 1)]}  # half owned
result7 = compute_set_completion(ufuc_set, checked7)
print("TEST 7: UFUC-style letter-numbered cards (card_number=None) don't crash and count correctly")
print(result7)
assert result7['mode'] == 'simple'
assert result7['tiers']['complete_set']['required'] == 28
assert result7['tiers']['complete_set']['owned'] == len(checked7)
print("PASS\n")

print("ALL TESTS PASSED")
