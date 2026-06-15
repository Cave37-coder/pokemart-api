from products.models import PokemonProduct
from django.db import transaction

# Old style: no variant in name brackets
# New style: has (Normal), (Reverse Holo), (Holofoil) etc in name

old_with_stock = PokemonProduct.objects.exclude(
    name__regex=r'\((Normal|Reverse Holo|Holofoil|1st Edition|Unlimited|1st Edition Holofoil|Unlimited Holofoil)\)$'
).filter(stock__gt=0).select_related('card_set')

print(f"Old records with stock to transfer: {old_with_stock.count()}", flush=True)

transferred = 0
not_found = []
errors = []

for old in old_with_stock:
    # Find matching new-style Normal variant in same set with same card_number
    # Old record name e.g. "Weedle", new style "Weedle (Normal)"
    candidates = PokemonProduct.objects.filter(
        card_set=old.card_set,
        card_number=old.card_number,
        name__regex=r'\((Normal|Holofoil)\)$'
    )
    
    if candidates.count() == 0:
        not_found.append(f"[{old.card_set.code}] #{old.card_number} {old.name} (stock={old.stock})")
        continue
    
    if candidates.count() == 1:
        new_rec = candidates.first()
    else:
        # Prefer Normal over Holofoil
        normal = candidates.filter(name__endswith='(Normal)').first()
        new_rec = normal if normal else candidates.first()
    
    try:
        with transaction.atomic():
            new_rec.stock += old.stock
            new_rec.save(update_fields=['stock'])
            transferred += 1
            print(f"  Transferred {old.stock} from '{old.name}' -> '{new_rec.name}' [{old.card_set.code}]", flush=True)
    except Exception as e:
        errors.append(f"Error: {old.name}: {e}")

print(f"\nTransferred: {transferred}", flush=True)
print(f"Not found: {len(not_found)}", flush=True)
for nf in not_found:
    print(f"  {nf}", flush=True)
if errors:
    print(f"Errors: {errors}", flush=True)

print("\nDone — ready to wipe old records if above looks correct.", flush=True)
