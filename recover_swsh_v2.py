from django.db import transaction
from products.models import CardSet, PokemonProduct
bad = PokemonProduct.objects.filter(pb_id="SSH-None-CC").first()
if bad:
    bad.pb_id = "TCGCSV-" + str(bad.tcgcsv_product_id)
    bad.save(update_fields=["pb_id"])
    print("Reverted pk=" + str(bad.pk) + " back to " + bad.pb_id)
else:
    print("No SSH-None-CC row found")
pairs = [("SWSH01","SSH"),("SWSH02","RCL"),("SWSH03","DAA"),("SWSH04","VIV"),("SWSH05","BST"),("SWSH06","CRE"),("SWSH07","EVS"),("SWSH08","FST")]
for old_code, new_code in pairs:
    try:
        with transaction.atomic():
            old_set = CardSet.objects.get(code=old_code)
            dup_set = CardSet.objects.filter(code=new_code).exclude(pk=old_set.pk).first()
            moved = 0
            if dup_set:
                moved = PokemonProduct.objects.filter(card_set=dup_set).update(card_set=old_set)
                dup_set.delete()
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
            print(old_code + " -> " + new_code + " | merged=" + str(moved) + " | total=" + str(PokemonProduct.objects.filter(card_set=old_set).count()) + " | pb_id_fixed=" + str(fixed) + " | skipped_none=" + str(skipped_none))
    except Exception as e:
        print(old_code + " -> " + new_code + " | FAILED: " + str(e))
