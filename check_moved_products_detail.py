from products.models import PokemonProduct, CardSet

# The 8 products we moved from PRIZEPACK -> MEE earlier
moved_ids = [405723, 405724, 405725, 405726, 405727, 405728, 405729, 405730]

print("--- Current state of the 8 moved products ---")
for pid in moved_ids:
    try:
        p = PokemonProduct.objects.get(id=pid)
        print(f"id={p.id} card_set={p.card_set.code if p.card_set else None} "
              f"price={p.price} stock={p.stock} tcgplayer_id={p.tcgplayer_id!r} "
              f"image_url={p.image_url!r} image_small_url={p.image_small_url!r} "
              f"is_active={p.is_active} name={p.name!r}")
    except PokemonProduct.DoesNotExist:
        print(f"id={pid} NOT FOUND")

# Cross-check: does the REAL MEE set (id=172) already have its own separate
# 001-008 basic energy cards that would now be duplicated by this move?
print("\n--- Existing MEE-set basic energy cards (card_number 1-8), pre-existing ---")
mee = CardSet.objects.get(id=172)
existing_mee_energy = PokemonProduct.objects.filter(
    card_set=mee, card_number__in=['1','2','3','4','5','6','7','8','001','002','003','004','005','006','007','008']
).exclude(id__in=moved_ids)
print(f"Found {existing_mee_energy.count()} other MEE products with matching card numbers:")
for p in existing_mee_energy:
    print(f"  id={p.id} card_number={p.card_number} price={p.price} image_url={p.image_url!r} name={p.name!r}")
