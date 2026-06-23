from products.models import PokemonProduct, CardSet

pp = CardSet.objects.get(id=143)
products = PokemonProduct.objects.filter(card_set=pp)
total = products.count()

has_number = products.exclude(number='').count()
blank_number = products.filter(number='').count()
print(f"Total PRIZEPACK products: {total}")
print(f"  with 'number' field populated: {has_number}")
print(f"  with 'number' blank: {blank_number}")

print("\n--- Sample of 15 with 'number' populated ---")
for p in products.exclude(number='')[:15]:
    print(f"  id={p.id} card_number={p.card_number} number={p.number!r} name={p.name!r}")

print("\n--- Sample of 15 with 'number' BLANK (the problem cases) ---")
for p in products.filter(number='')[:15]:
    print(f"  id={p.id} card_number={p.card_number} name={p.name!r}")

# Quick feasibility check: for products WITH a number denominator, how many
# CardSets actually have a matching total_cards value? (sanity check before
# building the full disambiguation script)
print("\n--- total_cards lookup sanity check ---")
sample = products.exclude(number='').exclude(number__contains='/').count()
print(f"'number' populated but no '/' in it (no denominator): {sample}")
