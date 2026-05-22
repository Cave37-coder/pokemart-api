import os, sys, django
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
sys.path.insert(0, os.getcwd())
django.setup()

from products.models import PokemonProduct
from django.db import transaction

# These orphans are real cards (1st Edition, Shining, RH-H variants)
# TCGCSV has no separate product ID for them
# Keep them active — they need manual pricing in admin

orphans = PokemonProduct.objects.filter(tcgcsv_product_id__isnull=True, price=0)
total = orphans.count()
print(f"Marking {total} legacy variant cards as active (no price — manual pricing needed)")

# Activate them so they show in admin for manual pricing
# Do NOT set a price — admin will handle these individually
with transaction.atomic():
    orphans.update(is_active=True)

print(f"Done. {total} cards now active and visible in admin.")
print()
print("These cards need manual prices in Django admin:")
print("  G1/G2  — 1st Edition WotC cards")
print("  N4     — Shining cards (Steelix, Raichu, Noctowl etc.)")
print("  LTR    — Radiant Collection subset")
print("  AQ/SK  — RH-H (Reverse Holo Holo) variants")
print("  PR-*   — Remaining unmatched promos")
