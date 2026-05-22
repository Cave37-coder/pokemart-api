import subprocess, sys

# Only sets with valid separate pokemontcg.io IDs
# Trainer Galleries (BRSTG/ASRTG/LORTG/SITTG) skipped - they are subsets of main sets
# Battle Academies, Trick or Trade, Prize Pack etc skipped - not in pokemontcg.io
SETS = [
    ("HIFSV",  "sm115"),      # Hidden Fates Shiny Vault
    ("SHFSV",  "swsh45"),     # Shining Fates Shiny Vault
    ("CELCC",  "cel25c"),     # Celebrations Classic Collection
    ("CRZGG",  "swsh12pt5"),  # Crown Zenith Galarian Gallery
    ("MEW",    "sv3pt5"),     # Scarlet & Violet 151
    ("LTRRC",  "xy8pt5"),     # Legendary Treasures Radiant Collection
    ("GENRC",  "g1"),         # Generations Radiant Collection
    ("RUM",    "ru1"),        # Rumble
    ("KSS",    "xy0"),        # Kalos Starter Set
    ("PR-NB",  "np"),         # Nintendo Black Star Promos
    ("PR-WB",  "basep"),      # Wizards Black Star Promos
    ("EXP",    "base5"),      # Expedition Base Set
    ("BSS",    "base6"),      # Base Set Shadowless
    ("LTRRC",  "xy8pt5"),     # Legendary Treasures RC
    ("MCD23",  "mcd23"),      # McDonalds 2023
    ("MCD24",  "mcd24"),      # McDonalds 2024
    ("SVE",    "sve"),        # Scarlet & Violet Energies
    ("TCGCL",  "tcg"),        # Trading Card Game Classic
    ("MEP",    "me1pt5"),     # Mega Evolution Promos
    ("MEE",    "me1pt5"),     # Mega Evolution Energies
]

for code, set_id in SETS:
    print(f"\n{'='*50}")
    print(f"Enriching [{code}] -> pokemontcg.io: {set_id}")
    result = subprocess.run([sys.executable, "manage.py", "enrich_set", set_id])
    if result.returncode != 0:
        print(f"  FAILED - skipping")

print("\nAll done!")
