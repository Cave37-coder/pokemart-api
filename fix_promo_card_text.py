"""
fix_promo_card_text.py -- one-off tidy-up of two card-text glitches from the
first sync_promos run (2026-10-27), already fixed in products/card_info.py:
  1. ability_name saved as "— Apple Drop" (TCGCSV writes "Ability — Name")
     -> "Apple Drop"
  2. a TCGCSV note stored as an attack, e.g. Hoopa 155/XY-P attack_1_name
     "This promotional card was printed in Japanese only." (no cost, no
     damage) -> attack cleared (the note is already in the description).

Dry run:  python manage.py shell -c "exec(open('fix_promo_card_text.py').read())"
Apply:    $env:APPLY="1"; python manage.py shell -c "exec(open('fix_promo_card_text.py').read())"; Remove-Item Env:APPLY
"""
import os
import re
from django.db.models import Q
from products.models import PokemonProduct

APPLY = os.environ.get("APPLY") == "1"
fixed = 0
for p in PokemonProduct.objects.filter(Q(ability_name__regex=r"^[—–:\-]\s*") | Q(ability_2_name__regex=r"^[—–:\-]\s*")):
    old = (p.ability_name, p.ability_2_name)
    p.ability_name = re.sub(r"^[—–:\-]\s*", "", p.ability_name or "")
    p.ability_2_name = re.sub(r"^[—–:\-]\s*", "", p.ability_2_name or "")
    print(f"{'FIX' if APPLY else 'WOULD FIX'} ability  {p.card_set.code if p.card_set else ''} {p.name}: {old[0]!r} -> {p.ability_name!r}")
    if APPLY:
        p.save(update_fields=["ability_name", "ability_2_name", "updated_at"])
    fixed += 1
for p in PokemonProduct.objects.filter(attack_1_cost="", attack_1_damage="", attack_1_text="", attack_1_name__endswith="."):
    print(f"{'FIX' if APPLY else 'WOULD FIX'} attack   {p.card_set.code if p.card_set else ''} {p.name}: clearing {p.attack_1_name!r}")
    if APPLY:
        if not p.description:
            p.description = p.attack_1_name
        p.attack_1_name = ""
        p.save(update_fields=["attack_1_name", "description", "updated_at"])
    fixed += 1
print(f"\n{fixed} row(s) {'fixed' if APPLY else 'to fix'}." + ("" if APPLY else " DRY RUN -- set APPLY=1 to apply."))
