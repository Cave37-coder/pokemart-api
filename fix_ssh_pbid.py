from products.models import CardSet, PokemonProduct
ss = CardSet.objects.get(code="SSH")
fixed = 0
for prod in PokemonProduct.objects.filter(card_set=ss, card_number__isnull=False):
    expected = "SSH-" + str(prod.card_number) + "-" + prod.variant_override
    if prod.pb_id != expected:
        prod.pb_id = expected
        prod.save(update_fields=["pb_id"])
        fixed += 1
print("SSH pb_id fixed:", fixed)
