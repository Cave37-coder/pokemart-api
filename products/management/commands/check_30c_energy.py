"""
check_30c_energy.py - PokeBulk SA (read-only)

Do we have the exact data for the 30th Celebration Basic Energy cards -- the
TCGplayer product list, the images and the pricing? Looks at BOTH 30th
Celebration groups on TCGCSV (24722 main set, 24837 Classic Collection) and at
what we hold in the database (sets 30C / 30CC), and prints:

  * every TCGplayer product that looks like an Energy card (name contains
    'Energy', or a Number that is not a normal set number), with its market price
  * every DB row in 30C / 30CC whose name contains 'Energy': price, stock,
    where its image lives (R2 / external / blank)
  * which TCGplayer Energy products are missing from the DB

  python manage.py check_30c_energy
"""
import requests
from django.core.management.base import BaseCommand

from products.models import PokemonProduct

GROUPS = {"30C": 24722, "30CC": 24837}
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
    help = "Read-only check of the 30th Celebration Energy cards: TCGplayer data vs our DB (images + pricing)."

    def handle(self, *args, **o):
        for code, gid in GROUPS.items():
            self.stdout.write(f"\n===== {code}  (TCGCSV group {gid}) =====")
            try:
                prods = requests.get(f"{BASE}/{gid}/products", headers=UA, timeout=90).json().get("results", [])
                prices = requests.get(f"{BASE}/{gid}/prices", headers=UA, timeout=90).json().get("results", [])
            except Exception as e:
                self.stdout.write(f"  fetch failed: {e}")
                continue
            by_pid_price = {}
            for r in prices:
                by_pid_price.setdefault(r["productId"], []).append(r)
            self.stdout.write(f"  TCGplayer: {len(prods)} products, {len(prices)} price rows")

            energy = [p for p in prods if "energy" in (p.get("name") or "").lower()]
            self.stdout.write(f"  TCGplayer products with 'Energy' in the name: {len(energy)}")
            have = {}
            for r in PokemonProduct.objects.filter(card_set__code=code).values(
                    "id", "name", "tcgcsv_product_id", "pb_id", "price", "stock", "image_url", "variant_override", "card_number"):
                if r["tcgcsv_product_id"]:
                    have.setdefault(int(r["tcgcsv_product_id"]), []).append(r)
                if r["pb_id"] and r["pb_id"].startswith("TCGCSV-"):
                    pid = r["pb_id"][7:].split("-")[0]
                    if pid.isdigit():
                        have.setdefault(int(pid), []).append(r)
            for p in sorted(energy, key=lambda x: x["productId"]):
                pr = by_pid_price.get(p["productId"], [])
                prtxt = ", ".join(f"{x.get('subTypeName')}: mkt ${x.get('marketPrice')}" for x in pr) or "no price rows"
                rows = have.get(p["productId"], [])
                state = "in DB" if rows else "MISSING from DB"
                self.stdout.write(f"   {p['productId']}  {p['name'][:46]:46} #{ext(p, 'Number') or '-':8} {prtxt}  -> {state}")
                for r in rows:
                    self.stdout.write(f"        DB id {r['id']}  {r['variant_override'] or 'N'}  R{r['price']}  stock {r['stock']}  image {where(r['image_url'])}")

            db_energy = PokemonProduct.objects.filter(card_set__code=code, name__icontains="energy")
            self.stdout.write(f"\n  DB rows named '*Energy*' in {code}: {db_energy.count()}")
            for r in db_energy.order_by("card_number", "variant_override")[:60]:
                self.stdout.write(f"   id {r.id}  {r.name[:40]:40} #{r.card_number or '-':6} {r.variant_override or 'N':4} "
                                  f"R{r.price}  stock {r.stock}  image {where(r.image_url)}  tcgcsv {r.tcgcsv_product_id or '-'}")

        # Any Energy-like rows sitting in OTHER sets that came from these groups
        self.stdout.write("\nNote: the main-set 'Basic Energy' cards are packed 1 per booster; TCGplayer may list them "
                          "under names like 'Grass Energy', 'Lightning Energy' etc., or not at all (in which case "
                          "the count above is 0 and they would need entering by hand + images from Serebii/Bulbapedia).")
