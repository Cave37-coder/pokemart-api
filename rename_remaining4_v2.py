from products.models import CardSet, PokemonProduct
pairs = [("SWSH09","BRS"),("SWSH10","ASR"),("SWSH11","LOR"),("SWSH12","SIT")]
for old_code, new_code in pairs:
    try:
        old_set = CardSet.objects.get(code=old_code)
        dup_set = CardSet.objects.filter(code=new_code).exclude(pk=old_set.pk).first()
        if dup_set:
            dup_count = PokemonProduct.objects.filter(card_set=dup_set).count()
            if dup_count > 0:
                PokemonProduct.objects.filter(card_set=dup_set).update(card_set=old_set)
            dup_set.delete()
        else:
            dup_count = 0
        old_set.code = new_code
        old_set.save(update_fields=["code"])
        fixed = 0
        skipped_none = 0
        for prod in PokemonProduct.objects.filter(card_set=old_set):
            if prod.card_number is None:
                skipped_none += 1
                continue
            expected = new_code + "-" + str(prod.card_number) + "-" + prod.variant_override
            if prod.pb_id != expected:
                prod.pb_id = expected
                prod.save(update_fields=["pb_id"])
                fixed += 1
        print(old_code + " -> " + new_code + " | dup_had=" + str(dup_count) + " | total=" + str(PokemonProduct.objects.filter(card_set=old_set).count()) + " | pb_id_fixed=" + str(fixed) + " | skipped_none=" + str(skipped_none))
    except Exception as e:
        print(old_code + " -> " + new_code + " | FAILED: " + str(e))
