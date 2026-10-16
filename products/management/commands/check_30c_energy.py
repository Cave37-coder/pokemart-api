"""
check_30c_energy.py - PokeBulk SA (read-only)

Where are the 30th Celebration Basic Energy cards, and do we have them?

TCGCSV does NOT put them in the 30th Celebration groups -- they are in group
24461 "MEE: Mega Evolution Energies" as "Basic <Type> Energy - 0NN (30th
Celebration)" (productIds 713248-713255, numbers 009-016, rarity Futuristic
Rare, Holofoil). This lists them, their TCGplayer market prices, and what the
database holds for each (any set): price, stock, image location, set.

  python manage.py check_30c_energy --skip-checks
"""
import requests
from django.core.management.base import BaseCommand

from products.models import PokemonProduct

GROUP = 24461
BASE = "https://tcgcsv.com/tcgplayer/3"
UA = {"User-Agent": "PokeBulkSA-30CEnergyCheck/1.0 (https://pokebulk.co.za)"}
R2 = "https://images.pokebulk.co.za/"


def ext(p, key):
    for e in p.get("extendedData", []) or []:
        if e.get("name") == key:
            return e.get("value")
    return None


def where(url):
    if not url:
        return "BLANK"
    return "R2" if url.startswith(R2) else "EXTERNAL"


class Command(BaseCommand):
    help = "Read-only check of the 30th Celebration Basic Energy cards (TCGCSV group 24461) vs our DB."

    def handle(self, *args, **o):
        prods = requests.get(f"{BASE}/{GROUP}/products", headers=UA, timeout=90).json().get("results", [])
        prices = requests.get(f"{BASE}/{GROUP}/prices", headers=UA, timeout=90).json().get("results", [])
        by_pid = {}
        for r in prices:
            by_pid.setdefault(r["productId"], []).append(r)
        cards = [p for p in prods if "30th" in (p.get("name") or "")]
        self.stdout.write(f"TCGCSV group {GROUP}: {len(prods)} products, {len(cards)} are 30th Celebration Energy")

        for p in sorted(cards, key=lambda x: x["productId"]):
            pid = p["productId"]
            pr = ", ".join(f"{x.get('subTypeName')}: mkt ${x.get('marketPrice')}" for x in by_pid.get(pid, [])) or "no price rows"
            self.stdout.write(f"\n{pid}  {p['name']}  #{ext(p, 'Number')}  {ext(p, 'Rarity')}  {pr}")
            rows = list(PokemonProduct.objects.select_related("card_set").filter(tcgcsv_product_id=pid))
            rows += [r for r in PokemonProduct.objects.select_related("card_set").filter(pb_id__startswith=f"TCGCSV-{pid}")
                     if r not in rows]
            if not rows:
                self.stdout.write("   -> NOT in the database")
            for r in rows:
                self.stdout.write(f"   -> DB id {r.id}  set {r.card_set.code if r.card_set else '-'}  {r.variant_override or 'N'}  "
                                  f"R{r.price}  stock {r.stock}  rarity {r.rarity}  image {where(r.image_url)}")

        mee = PokemonProduct.objects.filter(card_set__code="MEE")
        self.stdout.write(f"\nDB set MEE: {mee.count()} rows "
                          f"(images on R2: {mee.filter(image_url__startswith=R2).count()}, blank: {mee.filter(image_url='').count()})")
