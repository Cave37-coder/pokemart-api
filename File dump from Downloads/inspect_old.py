from products.models import PokemonProduct

# Show a sample of old records with stock to understand their structure
old_with_stock = PokemonProduct.objects.exclude(
    name__regex=r'\((Normal|Reverse Holo|Holofoil|1st Edition|Unlimited|1st Edition Holofoil|Unlimited Holofoil)\)$'
).filter(stock__gt=0).select_related('card_set')[:10]

print("OLD RECORDS WITH STOCK:", flush=True)
for p in old_with_stock:
    print(f"  id={p.id} set={p.card_set.code} name={p.name} number={p.card_number} csv_sku={p.csv_sku} tcgcsv_id={p.tcgcsv_product_id} stock={p.stock}", flush=True)

print("\nNEW RECORDS IN SAME SET (GEN):", flush=True)
new = PokemonProduct.objects.filter(
    card_set__code='GEN',
    name__regex=r'\((Normal|Reverse Holo|Holofoil)\)$'
).order_by('card_number')[:10]
for p in new:
    print(f"  id={p.id} name={p.name} number={p.card_number} csv_sku={p.csv_sku} tcgcsv_id={p.tcgcsv_product_id}", flush=True)
