from products.models import CardSet, PokemonProduct
ss = CardSet.objects.get(code="SSH")
print("SSH cardset id:", ss.pk, "name:", ss.name)
print("Total products under SSH:", PokemonProduct.objects.filter(card_set=ss).count())
bad = PokemonProduct.objects.filter(card_set=ss, card_number__isnull=True)
print("Products with card_number=None:", bad.count())
for p in bad:
    print("  pk=" + str(p.pk), "tcgcsv_id=" + str(p.tcgcsv_product_id), "pb_id=" + p.pb_id, "variant=" + p.variant_override, "name=" + p.name)
