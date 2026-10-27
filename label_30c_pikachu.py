"""
label_30c_pikachu.py -- add the Pikachu collection number (01/30 .. 30/30)
to the 30 chase Pikachu cards in 30th Celebration (2026-10-27).

Michael: "We need to label the 30th Pikachu's, I want their **/30 number on
the description too, not just their set numbers."

The 30 chase Pikachu are set numbers 023-052 of 30C; each also carries its
own Pikachu number 01/30-30/30 (023 = 01/30 ... 052 = 30/30, confirmed
against Bill's Archive's 30-Pikachu list by illustrator: 023 Ken Sugimori =
01/30, 047 Atsuko Nishida = 25/30, 052 Kazuki Minami = 30/30).

Renames "Pikachu" -> "Pikachu (14/30)" etc. on every row of those cards (all
variants, NM and played copies), so it shows on the site, search, pile,
invoices, pull sheets and the POS. Only the name changes; set number, price,
stock and images are untouched. The TCGCSV / bible syncs only set the name
when a row is first created, so a re-sync won't undo this.

Excludes the two Pikachu SIRs (149/150) and the Classic Collection Base Set
Pikachu -- they aren't part of the /30 run.

Dry run (default -- shows what would change):
    python manage.py shell -c "exec(open('label_30c_pikachu.py').read())"
Apply:
    $env:APPLY="1"; python manage.py shell -c "exec(open('label_30c_pikachu.py').read())"; Remove-Item Env:APPLY
"""
import os
import re

from products.models import PokemonProduct

APPLY = os.environ.get("APPLY") == "1"
FIRST, LAST = 23, 52  # set numbers 023-052 -> Pikachu 01/30-30/30

qs = (PokemonProduct.objects
      .filter(card_set__code="30C", card_number__gte=FIRST, card_number__lte=LAST, name__istartswith="Pikachu")
      .order_by("card_number", "variant_sort", "condition"))

changed = skipped = 0
for p in qs:
    n = p.card_number - FIRST + 1
    label = f"{n:02d}/30"
    base = re.sub(r"\s*\(\d{2}/30\)\s*$", "", p.name).strip()
    new_name = f"{base} ({label})"
    if p.name == new_name:
        skipped += 1
        continue
    print(f"{'UPDATE' if APPLY else 'WOULD UPDATE'}  #{p.card_number:03d}  {p.variant_override or 'N'}  {p.condition}  "
          f"{p.name!r} -> {new_name!r}  (id {p.id})")
    if APPLY:
        PokemonProduct.objects.filter(pk=p.pk).update(name=new_name)
    changed += 1

print(f"\n{qs.count()} matching row(s): {changed} {'updated' if APPLY else 'to update'}, {skipped} already labelled.")
if qs.count() < 30:
    print("NOTE: fewer than 30 rows found -- some of the 30 chase Pikachu may not be in the DB yet (run the 30C sync).")
if not APPLY:
    print("DRY RUN -- nothing written. Set APPLY=1 to apply.")
