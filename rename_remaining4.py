from products.models import CardSet, PokemonProduct
pairs = [("SWSH09","BRS"),("SWSH10","ASR"),("SWSH11","LOR"),("SWSH12","SIT")]
for old_code, new_code in pairs:
    cs = CardSet.objects.get(code=old_code)
    cs.code = new_code
    cs.save(update_fields=["code"])
    fixed = 0
    skipped_none = 0
    for prod in PokemonProduct.objects.filter(card_set=cs):
        if prod.card_number is None:
            skipped_none += 1
            continue
        expected = new_code + "-" + str(prod.card_number) + "-" + prod.variant_override
        if prod.pb_id != expected:
            prod.pb_id = expected
            prod.save(update_fields=["pb_id"])
            fixed += 1
    print(old_code + " -> " + new_code + " | id=" + str(cs.pk) + " | products=" + str(PokemonProduct.objects.filter(card_set=cs).count()) + " | pb_id_fixed=" + str(fixed) + " | skipped_none=" + str(skipped_none))
