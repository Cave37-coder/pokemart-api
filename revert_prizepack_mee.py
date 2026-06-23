from products.models import PokemonProduct, CardSet

DRY_RUN = False  # confirmed via dry run — applying now

pp = CardSet.objects.get(id=143)   # PRIZEPACK
mee = CardSet.objects.get(id=172)  # MEE

ids_to_revert = [405723, 405724, 405725, 405726, 405727, 405728, 405729, 405730]

targets = PokemonProduct.objects.filter(id__in=ids_to_revert, card_set=mee)
print(f"Found {targets.count()} of {len(ids_to_revert)} products currently under MEE to move back to PRIZEPACK:")
for p in targets.order_by('card_number'):
    print(f"  id={p.id} card_number={p.card_number} price={p.price} name={p.name!r}")

if DRY_RUN:
    print("\nDRY RUN — nothing changed. Set DRY_RUN = False and rerun to apply.")
else:
    updated = targets.update(card_set=pp)
    print(f"\nReverted {updated} products back to card_set=PRIZEPACK (id={pp.id}).")
