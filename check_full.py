from products.models import CardSet, PokemonProduct
pairs = [("SWSH01","SSH"),("SWSH02","RCL"),("SWSH03","DAA"),("SWSH04","VIV"),("SWSH05","BST"),("SWSH06","CRE"),("SWSH07","EVS"),("SWSH08","FST"),("SWSH09","BRS"),("SWSH10","ASR"),("SWSH11","LOR"),("SWSH12","SIT"),("BST","BRSTG")]
all_codes = sorted(set([c for pair in pairs for c in pair]))
rows = {c: list(CardSet.objects.filter(code=c)) for c in all_codes}
[print(c, "-> id=" + str(r.pk), "name=" + r.name, "products=" + str(PokemonProduct.objects.filter(card_set=r).count())) for c in all_codes for r in rows[c]]
[print(c, "-> NOT FOUND") for c in all_codes if not rows[c]]
