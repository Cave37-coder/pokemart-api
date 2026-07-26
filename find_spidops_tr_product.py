from products.models import PokemonProduct

print("Searching for all 'Spidops' products currently in the DB")
print("=" * 70)

matches = PokemonProduct.objects.filter(name__icontains="Spidops")

print(f"Found {matches.count()} product(s) with 'Spidops' in the name")
print("-" * 70)

for p in matches:
    print(f"id: {p.id}")
    print(f"  name: {p.name}")
    print(f"  card_set: {p.card_set}")
    print(f"  card_number: {p.card_number}")
    print(f"  variant_override: {p.variant_override}")
    print(f"  pb_id: {getattr(p, 'pb_id', 'N/A')}")
    print(f"  stock: {getattr(p, 'stock', 'N/A')}")
    print("-" * 70)

print()
print("Reminder: OrderItem 636 snapshot was:")
print("  product_name = \"Team Rocket's Spidops (Team Rocket)\"")
print("Look above for a product with card_set=ASC, variant_override=TR")
print("(or check if it's genuinely missing / needs recreating)")
