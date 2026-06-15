import json, os, sys, django
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
sys.path.insert(0, ".")
django.setup()

from products.management.commands.rebuild_from_tcgcsv import Command

# Group IDs for empty sets we need
TARGETS = {
    23237: "MEW",   # SV 151
    2594:  "HIFSV", # Hidden Fates Shiny Vault
    2781:  "SHFSV", # Shining Fates Shiny Vault
    2931:  "CELCC", # Celebrations Classic Collection
    3020:  "BRSTG", # Brilliant Stars TG
    3068:  "ASRTG", # Astral Radiance TG
    3172:  "LORTG", # Lost Origin TG
    17674: "SITTG", # Silver Tempest TG
    17689: "CRZGG", # Crown Zenith Galarian Gallery
    24451: "MEP",   # Mega Evolution Promos
    24461: "MEE",   # Mega Evolution Energies
    24587: "CRI",   # Chaos Rising - wait this is POR?
}

print("Checking group IDs match DB codes...")
with open("tcgcsv_all_products.json") as f:
    all_products = json.load(f)

print(f"Total TCGCSV products: {len(all_products):,}")
for gid, code in TARGETS.items():
    count = sum(1 for p in all_products if p.get("groupId") == gid)
    print(f"  group {gid} -> [{code}]: {count} products in TCGCSV")
