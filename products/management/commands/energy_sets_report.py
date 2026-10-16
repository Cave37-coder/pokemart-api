"""
energy_sets_report.py - PokeBulk SA (read-only)

Which sets do our Basic Energy cards live in, and which Energy cards does
TCGplayer (via TCGCSV) list for the newest Mega Evolution-era groups?

  python manage.py energy_sets_report --skip-checks
"""
import requests
from collections import defaultdict
from django.core.management.base import BaseCommand

from products.models import PokemonProduct

BASE = "https://tcgcsv.com/tcgplayer/3"
UA = {"User-Agent": "PokeBulkSA-EnergyReport/1.0 (https://pokebulk.co.za)"}
GROUPS = {"ASC": 24541, "MEG": 24380, "MEE": 24461, "30C": 24722, "MEP": 24451}


def ext(p, key):
    for e in p.get("extendedData", []) or []:
        if e.get("name") == key:
            return e.get("value")
    return None


class Command(BaseCommand):
    help = "Read-only: where do Energy cards live (DB sets) and what TCGCSV lists for the ME-era groups."

    def handle(self, *args, **o):
        self.stdout.write("== DB: rows whose name contains 'Energy', by set (Mega Evolution era) ==")
        qs = (PokemonProduct.objects.select_related("card_set")
              .filter(name__icontains="energy", card_set__code__in=list(GROUPS) + ["PFL", "POR", "PBL", "CRI", "DLR"]))
        by = defaultdict(list)
        for r in qs:
            by[r.card_set.code].append(r)
        for code, rows in sorted(by.items()):
            nums = sorted({str(r.card_number) for r in rows if r.card_number is not None})
            self.stdout.write(f"  {code}: {len(rows)} rows, card numbers {', '.join(nums[:30])}")
            for r in sorted(rows, key=lambda x: (x.card_number or 0, x.variant_override or ''))[:12]:
                self.stdout.write(f"      id {r.id} #{r.card_number} {r.variant_override or 'N'} {r.name[:46]}")

        for code, gid in GROUPS.items():
            self.stdout.write(f"\n== TCGCSV group {gid} ({code}): Energy products ==")
            try:
                prods = requests.get(f"{BASE}/{gid}/products", headers=UA, timeout=90).json().get("results", [])
            except Exception as e:
                self.stdout.write(f"  fetch failed: {e}")
                continue
            en = [p for p in prods if "energy" in (p.get("name") or "").lower()
                  or (ext(p, "Card Type") or "").lower().endswith("energy")]
            self.stdout.write(f"  {len(prods)} products, {len(en)} Energy-like")
            for p in sorted(en, key=lambda x: x["productId"])[:24]:
                self.stdout.write(f"   {p['productId']}  {p['name'][:52]:52} #{ext(p, 'Number')}  {ext(p, 'Rarity')}")
