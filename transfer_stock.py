from products.models import PokemonProduct
from django.db import transaction

# Old records: no variant suffix OR has (Holo) suffix (not Holofoil)
# Strategy: match by set + exact name where possible
# For (Holo) -> match to (Holofoil) in same set with same base name

old_with_stock = PokemonProduct.objects.exclude(
    name__regex=r'\((Normal|Reverse Holo|Holofoil|1st Edition|Unlimited|1st Edition Holofoil|Unlimited Holofoil)\)$'
).filter(stock__gt=0).select_related('card_set')

print(f"Old records with stock: {old_with_stock.count()}", flush=True)

transferred = 0
not_found = []

for old in old_with_stock:
    matched = None
    
    # Case 1: name ends with (Holo) -> find matching (Holofoil) 
    if old.name.endswith(' (Holo)'):
        base = old.name[:-7]  # strip ' (Holo)'
        matched = PokemonProduct.objects.filter(
            card_set=old.card_set,
            name=f"{base} (Holofoil)"
        ).first()
    
    # Case 2: name ends with (Reverse Holo) -> find exact match in new records
    elif old.name.endswith(' (Reverse Holo)'):
        matched = PokemonProduct.objects.filter(
            card_set=old.card_set,
            name=old.name,
            tcgcsv_product_id__isnull=False  # new record has tcgcsv_id
        ).first()
    
    # Case 3: plain name -> find (Normal) variant
    else:
        matched = PokemonProduct.objects.filter(
            card_set=old.card_set,
            name=f"{old.name} (Normal)"
        ).first()
        if not matched:
            matched = PokemonProduct.objects.filter(
                card_set=old.card_set,
                name=f"{old.name} (Holofoil)"
            ).first()
    
    if matched:
        try:
            with transaction.atomic():
                matched.stock += old.stock
                matched.save(update_fields=['stock'])
                transferred += 1
                print(f"  OK [{old.card_set.code}] '{old.name}' ({old.stock}) -> '{matched.name}'", flush=True)
        except Exception as e:
            not_found.append(f"ERROR [{old.card_set.code}] {old.name}: {e}")
    else:
        not_found.append(f"NO MATCH [{old.card_set.code}] #{old.card_number} '{old.name}' stock={old.stock}")

print(f"\nTransferred: {transferred}", flush=True)
print(f"Not matched: {len(not_found)}", flush=True)
for nf in not_found:
    print(f"  {nf}", flush=True)
