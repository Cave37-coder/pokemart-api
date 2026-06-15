import subprocess, sys

SETS = [
    ("CRZGG",  "swsh12pt5"),  # Crown Zenith Galarian Gallery
    ("SHFSV",  "swsh45"),     # Shining Fates Shiny Vault
    ("HIFSV",  "sm115"),      # Hidden Fates Shiny Vault
    ("BRSTG",  "swsh9pt5"),   # Brilliant Stars Trainer Gallery
    ("ASRTG",  "swsh10pt5"),  # Astral Radiance Trainer Gallery
    ("LORTG",  "swsh11pt5"),  # Lost Origin Trainer Gallery
    ("SITTG",  "swsh12pt5"),  # Silver Tempest Trainer Gallery - actually same as CRZGG?
    ("CELCC",  "cel25c"),     # Celebrations Classic Collection
    ("MEW",    "sv3pt5"),     # 151
    ("LTRRC",  "xy8pt5"),     # Legendary Treasures Radiant Collection
    ("CRI",    "sv9"),        # Chaos Rising
    ("MEP",    "me1pt5"),     # Mega Evolution Promos
    ("MEE",    "me1pt5"),     # Mega Evolution Energies
    ("PR-HS",  "hsp"),        # HGSS Promos
    ("RUM",    "ru1"),        # Rumble
]

for code, set_id in SETS:
    print(f"\nEnriching [{code}] with pokemontcg.io ID: {set_id}")
    subprocess.run([sys.executable, "manage.py", "enrich_set", set_id])
