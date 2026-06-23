from products.models import PokemonProduct

DRY_RUN = False  # confirmed zero stock via dry run — applying now

dup_ids = [447221, 447226]

rows = PokemonProduct.objects.filter(id__in=dup_ids)
print(f"Found {rows.count()} of {len(dup_ids)} target rows:")
for p in rows:
    print(f"  id={p.id} pb_id={p.pb_id} stock={p.stock} price={p.price} name={p.name!r}")

non_zero_stock = rows.exclude(stock=0)
if non_zero_stock.exists():
    print("\n!! STOPPING — one or more of these rows now has non-zero stock. Re-check before deleting.")
    for p in non_zero_stock:
        print(f"  id={p.id} stock={p.stock}")
elif DRY_RUN:
    print("\nDRY RUN — nothing deleted. Set DRY_RUN = False at the top and rerun to apply.")
else:
    deleted_count, _ = rows.delete()
    print(f"\nDeleted {deleted_count} row(s).")
