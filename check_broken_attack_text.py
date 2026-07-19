"""
check_broken_attack_text.py
Read-only diagnostic -- prints the raw stored attack_1_text/attack_2_text
for the Beedrill EX (CRI) card showing broken "{{TCG" template artifact
on the live site, to determine whether the corruption is in the stored
data or in frontend rendering.

Usage:
    python manage.py shell -c "exec(open('check_broken_attack_text.py').read())"
"""

from products.models import PokemonProduct

p = PokemonProduct.objects.filter(sku='TCGCSV-693453').first()
if not p:
    # Fall back to name+set search if SKU lookup fails
    p = PokemonProduct.objects.filter(name__icontains='Beedrill', card_set__code='CRI').first()

if not p:
    print("Could not find this card at all -- check the SKU/name.")
else:
    print(f"Found: {p.name} (id={p.id}, sku={p.sku}, pb_id={p.pb_id})")
    print()
    print("RAW attack_1_name:", repr(p.attack_1_name))
    print("RAW attack_1_damage:", repr(p.attack_1_damage))
    print("RAW attack_1_text:", repr(p.attack_1_text))
    print()
    print("RAW attack_2_name:", repr(p.attack_2_name))
    print("RAW attack_2_damage:", repr(p.attack_2_damage))
    print("RAW attack_2_text:", repr(p.attack_2_text))
    print()
    print(f"attack_1_text length: {len(p.attack_1_text or '')}")
    print(f"attack_2_text length: {len(p.attack_2_text or '')}")
