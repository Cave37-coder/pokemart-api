"""
audit_energy -- read-only Energy gap report, per era (2026-11-16).

Michael: Energy cards must be on the site, one Energy set per era, with every correct variant and image -- "we haven't
done our work properly and downloaded the correct info". This changes NOTHING in the database. For every set that has a
TCGplayer group it compares the Energy cards TCGplayer (TCGCSV) lists with what the site holds, and reports per era:

  * Energy products on TCGplayer that are not on the site at all
  * Energy cards on the site missing variants TCGplayer lists (Normal / Holofoil / Reverse Holofoil ...)
  * Energy cards on the site with no image, or an image that is not on our R2 CDN
  * the standalone Energy groups (SVE = Scarlet & Violet Energies, MEE = Mega Evolution Energies) and whether loaded

    python manage.py audit_energy                 # full audit (resumable -- finished groups are cached)
    python manage.py audit_energy --status        # show progress only
    python manage.py audit_energy --restart       # forget the cache and re-fetch everything
Writes energy_audit.csv (every energy card, both sides), energy_audit_cache.json and energy_audit_progress.txt.
"""
import csv
import json
import os
import re
import time
from collections import defaultdict
from datetime import datetime, timedelta

import requests
from django.core.management.base import BaseCommand

from products.models import PokemonProduct, CardSet
from products.management.commands.sync_blister_cosmos import TCGCSV_BASE, HEADERS
from products.management.commands.sync_tcgcsv import GROUP_CONFIG, SUBTYPE_MAP

CACHE_FILE = "energy_audit_cache.json"
PROGRESS_FILE = "energy_audit_progress.txt"
R2_PREFIX = "https://images.pokebulk.co.za"
BASIC_TYPES = ("grass", "fire", "water", "lightning", "psychic", "fighting", "darkness", "metal", "fairy", "dragon", "colorless")
STANDALONE_ENERGY_GROUPS = {"SVE": 24382, "MEE": 24461}
ERA_NEW_TO_OLD = ["MEG", "SV", "SWSH", "SM", "XY", "BW", "HGSS", "DP", "EX", "WotCO", "WotCL", "WotCN", "WotC"]


def clean(name):
    """Strip every trailing decoration, in any order: '- 104/109', '[Reverse Holofoil]', '(Brilliant Stars)', '(Secret)'.
    ('Basic Lightning Energy - 012 (30th Celebration)' has BOTH a number and a bracket -- the old version missed it.)"""
    n = re.sub(r"\s*\[[^\]]*\]", "", name or "")
    patterns = (r"\s*-\s*\d+(/\d+)?\s*$",                        # "- 104/109"
                r"\s*\((?:[^()]|\([^()]*\))*\)\s*$")             # "(No E-Reader)", "(Brilliant Stars) (Secret)" ...
    changed = True
    while changed:
        changed = False
        for pat in patterns:
            m = re.sub(pat, "", n)
            if m != n:
                n, changed = m, True
    return n.strip()


def energy_kind(name):
    """'basic' / 'special' / '' (not an energy card). Name based -- PokemonProduct.supertype is unreliable."""
    n = clean(name)
    low = n.lower()
    if not low.endswith("energy"):
        return ""
    if low.startswith("energy "):          # "Energy Search"... never ends in Energy anyway, but be safe
        return ""
    stem = re.sub(r"^basic\s+", "", low)
    stem = re.sub(r"\s+energy$", "", stem)
    return "basic" if stem in BASIC_TYPES else "special"


def fmt_td(sec):
    return str(timedelta(seconds=int(max(sec, 0))))


class Command(BaseCommand):
    help = "Read-only audit of Energy cards: TCGplayer vs the site, per era (see module docstring)."

    def add_arguments(self, parser):
        parser.add_argument("--status", action="store_true")
        parser.add_argument("--restart", action="store_true")
        parser.add_argument("--csv", default="energy_audit.csv")

    # -- cache --------------------------------------------------------------
    def load_cache(self):
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def save_cache(self):
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(self.cache, f)

    def fetch(self, url):
        for attempt in range(3):
            try:
                r = requests.get(url, headers=HEADERS, timeout=30)
                r.raise_for_status()
                return r.json().get("results", [])
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(3)

    def energy_for_group(self, gid):
        key = str(gid)
        if key in self.cache:
            return self.cache[key]
        prods = self.fetch(f"{TCGCSV_BASE}/{gid}/products")
        keep = {}
        for p in prods:
            kind = energy_kind(p.get("name"))
            if not kind:
                continue
            ext = {e.get("name"): e.get("value") for e in (p.get("extendedData") or [])}
            keep[str(p["productId"])] = {"name": p.get("name"), "kind": kind, "number": ext.get("Number", ""),
                                         "rarity": ext.get("Rarity", ""), "subtypes": []}
        if keep:
            for pr in self.fetch(f"{TCGCSV_BASE}/{gid}/prices"):
                k = str(pr.get("productId"))
                if k in keep:
                    sub = pr.get("subTypeName") or ""
                    if sub not in keep[k]["subtypes"]:
                        keep[k]["subtypes"].append(sub)
        self.cache[key] = keep
        self.save_cache()
        time.sleep(0.1)
        return keep

    # -- main ---------------------------------------------------------------
    def handle(self, *args, **o):
        if o["restart"] and os.path.exists(CACHE_FILE):
            os.remove(CACHE_FILE)
        self.cache = self.load_cache()

        sets = {s.code: s for s in CardSet.objects.select_related("era")}
        code_gid = {code: gid for code, (gid, _n, _e) in GROUP_CONFIG.items()}
        for code, gid in STANDALONE_ENERGY_GROUPS.items():
            code_gid.setdefault(code, gid)
        groups = sorted({(code, gid) for code, gid in code_gid.items()})
        done_cached = sum(1 for _c, g in groups if str(g) in self.cache)

        if o["status"]:
            self.stdout.write(f"Fetched {done_cached}/{len(groups)} TCGplayer groups so far.")
            return

        # ---- site side ----------------------------------------------------
        self.stdout.write("Reading the site's Energy cards...")
        db = defaultdict(lambda: defaultdict(lambda: {"variants": set(), "image": True, "r2": True, "name": "", "set": "", "kind": ""}))
        rows = (PokemonProduct.objects.filter(condition="NM", name__icontains="energy")
                .values_list("card_set__code", "tcgcsv_product_id", "name", "variant_override", "image_url"))
        site_total = 0
        for code, pid, name, var, img in rows:
            kind = energy_kind(name)
            if not kind:
                continue
            site_total += 1
            d = db[code][pid if pid else f"noid:{name}"]
            d["variants"].add(var or "N")
            d["name"], d["set"], d["kind"] = name, code, kind
            if not img:
                d["image"] = False
                d["r2"] = False
            elif not img.startswith(R2_PREFIX):
                d["r2"] = False
        self.stdout.write(f"  {site_total} Energy rows on the site.\n")

        # ---- TCGplayer side (resumable, with progress) ---------------------
        t0, fetched = time.time(), 0
        for i, (code, gid) in enumerate(groups, 1):
            if str(gid) in self.cache:
                continue
            el = time.time() - t0
            eta = (el / fetched) * (len(groups) - i) if fetched else 0
            line = f"[{i}/{len(groups)}] {100 * i // len(groups):>3}%  {code:9} group {gid}  elapsed {fmt_td(el)}  ETA ~{fmt_td(eta) if fetched else '...'}"
            self.stdout.write(line)
            with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
                f.write(f"Energy audit  {datetime.now():%Y-%m-%d %H:%M:%S}\n{line}\n")
            try:
                self.energy_for_group(gid)
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"    fetch failed for {code}/{gid}: {str(e)[:100]} (run again to retry)"))
            fetched += 1

        # ---- compare ---------------------------------------------------------
        out_rows = []
        per_era = defaultdict(lambda: defaultdict(int))
        for code, gid in groups:
            s = sets.get(code)
            era = (s.era.code if s and s.era else "(set not on site)")
            tc = self.cache.get(str(gid), {})
            site_cards = db.get(code, {})
            site_by_pid = {str(k): v for k, v in site_cards.items() if not str(k).startswith("noid:")}
            for pid, info in tc.items():
                want = {SUBTYPE_MAP.get(sub, "N") for sub in info["subtypes"]} or {"N"}
                have = site_by_pid.get(pid)
                per_era[era]["tcgplayer_energy"] += 1
                if have is None:
                    status = "MISSING on site"
                    per_era[era]["missing_products"] += 1
                else:
                    missing_v = want - have["variants"]
                    status = "ok" if not missing_v else "missing variants: " + ",".join(sorted(missing_v))
                    if missing_v:
                        per_era[era]["missing_variants"] += 1
                    if not have["image"]:
                        status += " | NO IMAGE"
                        per_era[era]["no_image"] += 1
                    elif not have["r2"]:
                        status += " | image not on R2"
                        per_era[era]["not_r2"] += 1
                # "Released with": the product/set named in TCGplayer's own name, e.g.
                # "Basic Grass Energy [Cracked Ice Holo | Terapagos Ultra-Premium Collection]" -> the UPC;
                # otherwise the set the card was printed in. (Michael 2026-11-16: the release set -- even a UPC --
                # must be in the Energy card's name.)
                m = re.search(r"[\[(]([^\])]+)[\])]\s*$", info["name"] or "")
                released_with = (m.group(1).split("|")[-1].strip() if m and "|" in m.group(1) else (s.name if s else code))
                out_rows.append([era, code, gid, pid, info["name"], info["kind"], info["number"], info["rarity"],
                                 ",".join(sorted(want)), ",".join(sorted(have["variants"])) if have else "", status,
                                 released_with, " | ".join(info["subtypes"])])
            for pid, d in site_cards.items():
                per_era[era]["site_energy_cards"] += 1

        self.stdout.write("\n=== Energy per era (TCGplayer vs site) ===")
        order = [e for e in ERA_NEW_TO_OLD if e in per_era] + sorted(e for e in per_era if e not in ERA_NEW_TO_OLD)
        hdr = f"{'era':18} {'TCGplayer':>9} {'on site':>8} {'missing':>8} {'missing var':>11} {'no image':>9} {'not R2':>7}"
        self.stdout.write(hdr)
        for era in order:
            r = per_era[era]
            self.stdout.write(f"{era:18} {r['tcgplayer_energy']:>9} {r['site_energy_cards']:>8} {r['missing_products']:>8} "
                              f"{r['missing_variants']:>11} {r['no_image']:>9} {r['not_r2']:>7}")
        self.stdout.write("\n=== Standalone Energy groups ===")
        for code, gid in STANDALONE_ENERGY_GROUPS.items():
            n_tc = len(self.cache.get(str(gid), {}))
            self.stdout.write(f"  {code} (group {gid}): TCGplayer {n_tc} energy products | set on site: {'yes' if code in sets else 'NO'} | "
                              f"site energy cards: {len(db.get(code, {}))}")
        no_group = [c for c in db if c is not None and c not in code_gid]
        if no_group:
            self.stdout.write(f"\nSite sets with Energy rows but no TCGplayer group mapping (not audited): {', '.join(sorted(no_group))}")
        if None in db:
            self.stdout.write(self.style.WARNING(f"\n{len(db[None])} Energy card(s) on the site have NO set assigned -- listed in the CSV as set '(none)'."))
            for pid, d in db[None].items():
                out_rows.append(["(none)", "(none)", "", pid if not str(pid).startswith("noid:") else "", d["name"], d["kind"], "", "",
                                 "", ",".join(sorted(d["variants"])), "SITE CARD WITH NO SET", "", ""])

        with open(o["csv"], "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["era", "set", "group", "tcgcsv_product_id", "name", "kind", "number", "rarity",
                        "tcgplayer_variants", "site_variants", "status", "released_with", "tcgplayer_subtypes"])
            w.writerows(out_rows)
        self.stdout.write(self.style.SUCCESS(f"\nWrote {len(out_rows)} rows to {o['csv']}. Nothing in the database was changed."))
