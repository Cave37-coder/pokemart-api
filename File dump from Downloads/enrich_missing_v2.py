import os, sys, django, time
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
sys.path.insert(0, "C:/Users/texca/pokemart-api")
django.setup()
from django.core.management import call_command

# ALL missing sets cross-referenced from Pokellector, Pikawiz, PokeBeach, store CSV
MISSING = [
    # SWSH Trainer Galleries
    "swsh9tg",      # Brilliant Stars Trainer Gallery (30 cards)
    "swsh10tg",     # Astral Radiance Trainer Gallery (30 cards)
    "swsh11tg",     # Lost Origin Trainer Gallery (30 cards)
    "swsh12tg",     # Silver Tempest Trainer Gallery (30 cards)
    "swsh12pt5gg",  # Crown Zenith Galarian Gallery (70 cards)
    # SWSH Special
    "swsh45sv",     # Pokemon Futsal Promos (5 cards)
    # SV Special
    "sve",          # Scarlet & Violet Energies (24 cards)
    "mcd23",        # McDonalds Match Battle 2023
    "mcd25",        # McDonalds Dragon Discovery 2025
    # Play! Pokemon Prize Packs - COMPLETELY MISSING
    "prf",          # Prize Pack Series One (170 cards)
    "prf2",         # Prize Pack Series Two (154 cards)
    "prf3",         # Prize Pack Series Three (163 cards)
    "prf4",         # Prize Pack Series Four (86 cards)
    "prf5",         # Prize Pack Series Five (94 cards)
    # Mega Evolution
    "me4",          # Chaos Rising (May 2026, 130 cards)
    "mep",          # Mega Evolution Black Star Promos
]

print(f"Enriching {len(MISSING)} missing sets...")
print("=" * 60)
failed = []
for i, set_id in enumerate(MISSING, 1):
    print(f"\n[{i}/{len(MISSING)}] {set_id}")
    try:
        call_command("enrich_set", set_id, verbosity=1)
    except Exception as e:
        print(f"  FAILED: {e}")
        failed.append((set_id, str(e)))
    time.sleep(2)

print("\n" + "=" * 60)
print(f"Done. {len(MISSING)-len(failed)} succeeded, {len(failed)} failed.")
if failed:
    for s, e in failed:
        print(f"  {s}: {e}")
