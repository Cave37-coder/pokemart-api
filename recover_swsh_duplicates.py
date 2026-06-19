from products.models import CardSet, PokemonProduct
pairs = [("SWSH01","SSH"),("SWSH02","RCL"),("SWSH03","DAA"),("SWSH04","VIV"),("SWSH05","BST"),("SWSH06","CRE"),("SWSH07","EVS"),("SWSH08","FST")]
for old_code, new_code in pairs:
    old_set = CardSet.objects.get(code=old_code)
    dup_set = CardSet.objects.filter(code=new_code).exclude(pk=old_set.pk).first()
    moved = 0
    if dup_set:
        moved = PokemonProduct.objects.filter(card_set=dup_set).update(card_set=old_set)
        dup_set.delete()
    old_set.code = new_code
    old_set.save(update_fields=["code"])
    fixed = 0
    for prod in PokemonProduct.objects.filter(card_set=old_set):
        expected = new_code + "-" + str(prod.card_number) + "-" + prod.variant_override
        if prod.pb_id != expected:
            prod.pb_id = expected
            prod.save(update_fields=["pb_id"])
            fixed += 1
    print(old_code + " -> " + new_code + " | merged " + str(moved) + " products from duplicate | total now " + str(PokemonProduct.objects.filter(card_set=old_set).count()) + " | pb_id fixed " + str(fixed))
