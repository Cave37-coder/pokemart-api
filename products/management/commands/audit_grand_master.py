"""
audit_grand_master -- read-only gap report for the Grand Master Set work (2026-11-15).

Michael: deck exclusives, 30th Celebration stamped prints and promos must be on the site and the
checklists so a Grand Master Set can be offered in Collections. This changes NOTHING in the
database. It reads TCGplayer's "Deck Exclusives" (group 1840) and "Blister Exclusives" (group 2289)
from TCGCSV, tries to match every card to its parent set card using the same rules as
sync_blister_cosmos, and writes grand_master_audit.csv plus a summary here.

    python manage.py audit_grand_master
    python manage.py audit_grand_master --groups 1840,2289 --csv my_audit.csv
"""
import csv
import re
from collections import Counter, defaultdict

from django.core.management.base import BaseCommand
from django.db.models import Count

from products.models import PokemonProduct
from products.promo_links import is_promo_home
from products import card_info as info
from products.management.commands import sync_blister_cosmos as sbc
from products.management.commands.sync_tcgcsv import GROUP_CONFIG


def classify(name, rarity):
    low = (name or "").lower()
    if "cosmo" in low:
        return "CH cosmos holo"
    if "30th" in low:
        return "30th stamp"
    if any(w in low for w in ("cracked ice", "tinsel", "reverse")):
        return "other pattern"
    if "non-holo" in low or "non holo" in low:
        return "DE non-holo"
    if "holo" in low or "holo" in (rarity or "").lower():
        return "DEH holo"
    return "DE non-holo"


class Command(BaseCommand):
    help = "Read-only audit: promos linked, cosmos holo, deck exclusives and 30th stamped prints vs the site."

    def add_arguments(self, parser):
        parser.add_argument("--groups", default="1840,2289")
        parser.add_argument("--csv", default="grand_master_audit.csv")

    def handle(self, *args, **o):
        # 1) promos linked into main sets
        self.stdout.write("=== 1. Promos on checklists ===")
        promo_sets = defaultdict(lambda: [0, 0])
        qs = PokemonProduct.objects.filter(condition="NM").annotate(n_links=Count("also_in_sets", distinct=True))
        for code, linked in qs.values_list("card_set__code", "n_links"):
            if is_promo_home(code):
                promo_sets[code][0] += 1
                promo_sets[code][1] += 1 if linked else 0
        tot = sum(v[0] for v in promo_sets.values())
        lnk = sum(v[1] for v in promo_sets.values())
        self.stdout.write(f"{tot} promo products across {len(promo_sets)} promo sets; {lnk} linked to a main set, {tot - lnk} NOT linked.")
        for code, (t, l) in sorted(promo_sets.items(), key=lambda kv: -(kv[1][0] - kv[1][1]))[:15]:
            self.stdout.write(f"  {code:10} {t:>5} promos, {l:>5} linked, {t - l:>5} unlinked")

        # 2) variants already on site
        self.stdout.write("\n=== 2. Extra prints already on the site ===")
        for v in ("CH", "DE", "DEH", "ST"):
            self.stdout.write(f"  variant {v}: {PokemonProduct.objects.filter(variant_override=v, condition='NM').count()}")
        self.stdout.write(f"  names containing '30th': {PokemonProduct.objects.filter(name__icontains='30th').count()}")

        # 3) TCGCSV groups
        b = sbc.Command()
        b.stdout, b.style, b._group_cache = self.stdout, self.style, {}
        code_to_gid = {code: gid for code, (gid, _n, _e) in GROUP_CONFIG.items()}
        rows, summary, reasons = [], Counter(), Counter()
        have_ids = set(PokemonProduct.objects.exclude(tcgcsv_product_id__isnull=True).values_list("tcgcsv_product_id", flat=True))
        for gid in [int(g) for g in o["groups"].split(",") if g.strip()]:
            prods = b.group_products(gid)
            self.stdout.write(f"\n=== 3. TCGCSV group {gid}: {len(prods)} products ===")
            for p in prods:
                pid, name = p["productId"], (p.get("name") or "").strip()
                ext = p.get("extendedData") or []
                number_raw, rarity = info.ext(ext, "Number"), info.ext(ext, "Rarity")
                if not number_raw:
                    continue
                cls = classify(name, rarity)
                base, num, den = sbc.parse_blister_name(name, number_raw)
                status, parent_set, parent_name, why = "", "", "", ""
                if pid in have_ids:
                    status = "already on site"
                else:
                    parent, why = b.find_parent(base, num, den, code_to_gid)
                    if parent is None and num is not None:
                        m = re.search(r"(\d+)\s*/\s*(\d+)", name)
                        if m and int(m.group(1)) == num and int(m.group(2)) != den:
                            parent, why = b.find_parent(base, num, int(m.group(2)), code_to_gid)
                    if parent is not None:
                        status, parent_set, parent_name, why = "matched", parent.card_set.code, parent.name, ""
                    else:
                        status = "UNMATCHED"
                        reasons[re.sub(r"\d+", "#", why)[:70]] += 1
                summary[(gid, cls, status)] += 1
                rows.append([gid, pid, name, number_raw, rarity, cls, status, parent_set, parent_name, why])

        self.stdout.write("\n=== Summary (group, kind, status: count) ===")
        for (gid, cls, status), n in sorted(summary.items()):
            self.stdout.write(f"  {gid}  {cls:15} {status:16} {n:>5}")
        if reasons:
            self.stdout.write("\n=== Top reasons for UNMATCHED ===")
            for r, n in reasons.most_common(8):
                self.stdout.write(f"  {n:>4}  {r}")
        with open(o["csv"], "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["group", "tcgcsv_product_id", "name", "number", "rarity", "kind", "status", "parent_set", "parent_name", "reason"])
            w.writerows(rows)
        self.stdout.write(self.style.SUCCESS(f"\nWrote {len(rows)} rows to {o['csv']}. Nothing in the database was changed."))
