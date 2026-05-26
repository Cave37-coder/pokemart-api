from django.db import transaction
from products.models import CardSet, PokemonProduct

OLD_CODES = ['ASR','BRS','CEL','CELCC','CHP','CRE','DAA','EVS','FST','LOR','RCL','SHF','SIT','SSH','VIV','PR-SW']

with transaction.atomic():
    for code in OLD_CODES:
        try:
            count = PokemonProduct.objects.filter(card_set__code=code).delete()
            cs = CardSet.objects.get(code=code)
            cs.delete()
            print(f"Deleted {code} ({count[0]} products)")
        except CardSet.DoesNotExist:
            print(f"{code} not found")

print("Done!")
