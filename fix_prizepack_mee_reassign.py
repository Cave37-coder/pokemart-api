from products.models import PokemonProduct, CardSet

DRY_RUN = False  # confirmed via dry run — applying now

pp = CardSet.objects.get(code='PRIZEPACK')
mee = CardSet.objects.get(id=172)  # 'Mega Evolution Energies'

# Only the genuine TCGCSV-sourced rows get moved. The two manually-entered
# PRIZEPACK-*-H/N stock rows are deliberately left untouched here.
targets = PokemonProduct.objects.filter(
    card_set=pp,
    name__icontains=' - MEE',
    pb_id__startswith='TCGCSV-',
)

print(f"Found {targets.count()} TCGCSV-sourced products to move from PRIZEPACK -> MEE:")
for p in targets.order_by('card_number'):
    print(f"  id={p.id} pb_id={p.pb_id} card_number={p.card_number} stock={p.stock} name={p.name!r}")

if DRY_RUN:
    print("\nDRY RUN — nothing changed. Set DRY_RUN = False at the top and rerun to apply.")
else:
    updated = targets.update(card_set=mee)
    print(f"\nUpdated {updated} products to card_set=MEE (id={mee.id}).")

# --- Stock check on the two manually-entered duplicate rows, for your decision ---
print("\n--- Manually-entered duplicate rows (NOT touched by this script) ---")
for dup_id in [447221, 447226]:
    try:
        d = PokemonProduct.objects.get(id=dup_id)
        print(f"  id={d.id} pb_id={d.pb_id} stock={d.stock} price={d.price} name={d.name!r}")
    except PokemonProduct.DoesNotExist:
        print(f"  id={dup_id} not found (already removed?)")
