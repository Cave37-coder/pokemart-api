import json, os, sys, django

os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
sys.path.insert(0, os.getcwd())
django.setup()

from products.models import CardSet, Era, PokemonProduct

# Load TCGCSV data
with open("tcgcsv_all_products.json") as f:
    tcgcsv = json.load(f)

with open("tcgcsv_groups.json") as f:
    groups = json.load(f)

# Build TCGCSV group lookup
tcg_by_gid = {}
for g in groups:
    gid = str(g.get("groupId") or g.get("id"))
    tcg_by_gid[gid] = g

# Get all DB sets
db_sets = list(CardSet.objects.select_related("era").order_by("era__code", "release_date"))
db_codes = {cs.code for cs in db_sets}

print("=" * 90)
print(f"{'GID':>8} | {'TCGCSV ABBR':15} | {'TCGCSV NAME':45} | {'CARDS':>6} | DB MATCH")
print("=" * 90)

# Map each TCGCSV group to DB
matched = []
unmatched = []

for gid_str, data in sorted(tcgcsv.items(), key=lambda x: int(x[0])):
    gid = int(gid_str)
    name = data["name"]
    abbr = data.get("abbreviation", "")
    cards = len(data.get("cards", []))
    
    if cards == 0:
        continue  # skip empty groups
    
    # Try match DB set by abbreviation
    db_match = None
    for cs in db_sets:
        if cs.code.upper() == abbr.upper():
            db_match = cs
            break
    
    if not db_match:
        # Try partial name match
        name_lower = name.lower()
        for cs in db_sets:
            if cs.name.lower() in name_lower or name_lower in cs.name.lower():
                db_match = cs
                break

    if db_match:
        db_count = PokemonProduct.objects.filter(card_set=db_match).count()
        matched.append((gid, abbr, name, cards, db_match.code, db_count))
        print(f"{gid:>8} | {abbr:15} | {name:45} | {cards:>6} | ✓ DB:{db_match.code} ({db_count} records)")
    else:
        unmatched.append((gid, abbr, name, cards))
        print(f"{gid:>8} | {abbr:15} | {name:45} | {cards:>6} | ✗ NOT IN DB")

print()
print("=" * 90)
print(f"TCGCSV groups with cards: {len(matched) + len(unmatched)}")
print(f"Matched to DB sets:       {len(matched)}")
print(f"NOT in DB (missing sets): {len(unmatched)}")
print()
print("MISSING SETS (need to be added):")
print("-" * 70)
total_missing_cards = 0
for gid, abbr, name, cards in unmatched:
    print(f"  gid={gid:6} | {abbr:15} | {name:45} | {cards} cards")
    total_missing_cards += cards
print(f"\nTotal cards in missing sets: {total_missing_cards}")

# Save report
report = {"matched": matched, "unmatched": unmatched}
with open("tcgcsv_db_mapping.json", "w") as f:
    json.dump(report, f, indent=2)
print("\nSaved tcgcsv_db_mapping.json")
