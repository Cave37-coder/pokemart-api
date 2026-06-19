from products.models import CardSet, PokemonProduct
ss = CardSet.objects.get(code="SSH")
mismatched = []
for prod in PokemonProduct.objects.filter(card_set=ss, card_number__isnull=False):
    expected = "SSH-" + str(prod.card_number) + "-" + prod.variant_override
    if prod.pb_id != expected:
        mismatched.append((prod.pk, prod.pb_id, expected))
print("SSH total card products:", PokemonProduct.objects.filter(card_set=ss, card_number__isnull=False).count())
print("Mismatched pb_id count:", len(mismatched))
for pk, old, new in mismatched[:10]:
    print("  pk=" + str(pk) + "  current=" + old + "  expected=" + new)
