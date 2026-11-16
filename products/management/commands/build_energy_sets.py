"""
build_energy_sets -- Energy cards done properly, one Energy set per era (2026-11-16).

Michael: "add the Energy to each era ... go through every Energy set and have all the correct Variants and images",
"have the name of the set it was released with in the name, even if it was released in a UPC (Terapagos Cracked Ice
Energy set)". Run `audit_energy` first (it writes energy_audit_cache.json, which this command reads).

Steps (all idempotent -- safe to re-run; DRY RUN unless --apply):
  1 orphans   Energy rows with NO set (Prize Pack Series energies, N print) -> their real set (PRIZEPACK)
  2 sync      for every Energy product TCGplayer lists: create what is missing -- whole cards (SVE incl. the Terapagos
              UPC Cracked Ice Energy, MEE, Delta Reign, TCG Classic, SM Trainer Kits) and missing variants
              (Normal / Reverse Holo / Holo / Cosmos Holo / Cracked Ice). Price from TCGplayer (no price -> 0 = "TBC"),
              image re-hosted on R2 (CLAUDE.md rule)
  3 images    Energy images still pointing outside R2 (SM9 / SM Trainer Kit ...) -> R2
  4 eraset    create "<Era> Energies" sets and link every Energy card of that era into them (also_in_sets)
  5 names     put the set / product it was released with into every Energy card's name, e.g.
              "Grass Energy (Brilliant Stars)", "Basic Grass Energy (Terapagos ex Ultra-Premium Collection)".
              Old -> new names are saved to energy_rename_log.json (so it can be undone)

    python manage.py build_energy_sets                       # dry run of everything
    python manage.py build_energy_sets --apply               # do it
    python manage.py build_energy_sets --apply --step sync   # one step only (orphans|sync|images|eraset|names)
    python manage.py build_energy_sets --status
Prints [done/total] progress per step and writes energy_build_progress.txt.
"""
import json
import os
import re
import time
from datetime import datetime, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import connection, transaction

from products.models import PokemonProduct, CardSet, Era
from products import card_info as info
from products.management.commands.audit_energy import energy_kind, clean, CACHE_FILE, STANDALONE_ENERGY_GROUPS
from products.management.commands.sync_blister_cosmos import TCGCSV_BASE, HEADERS
from products.management.commands.sync_tcgcsv import GROUP_CONFIG, SUBTYPE_MAP, _get_rate, _zar_price

PROGRESS_FILE = "energy_build_progress.txt"
RENAME_LOG = "energy_rename_log.json"
R2_PREFIX = "https://images.pokebulk.co.za"
STEPS = ["orphans", "sync", "images", "fillgaps", "eraset", "names"]

# TCGplayer group code -> the CardSet code the site uses.
SET_ALIAS = {"ME06": "DLR"}

# One Energy set per era: era code -> (set code, set name). SVE / MEE already exist as TCGplayer's own Energy sets.
ERA_ENERGY_SETS = {
    "MEG": ("MEE", "Mega Evolution Energies"),
    "SV": ("SVE", "Scarlet & Violet Energies"),
    "SWSH": ("SWSHE", "Sword & Shield Energies"),
    "SM": ("SME", "Sun & Moon Energies"),
    "XY": ("XYE", "XY Energies"),
    "BW": ("BWE", "Black & White Energies"),
    "HGSS": ("HGSSE", "HeartGold SoulSilver Energies"),
    "DP": ("DPE", "Diamond & Pearl Energies"),
    "EX": ("EXE", "EX Era Energies"),
    "WotCO": ("WOTCOE", "e-Card Energies"),
    "WotCL": ("WOTCLE", "Legendary Collection Energies"),
    "WotCN": ("WOTCNE", "Neo Energies"),
    "WotC": ("WOTCE", "WotC Base Energies"),
}

# "Released with" for the standalone Energy groups, by printed number (edit here if a label is wrong).
# SVE 009-016 are the Terapagos ex Ultra-Premium Collection energies (Normal / Holo / Cracked Ice Holo).
RELEASED_WITH_BY_NUMBER = {
    ("SVE", range(9, 17)): "Terapagos ex Ultra-Premium Collection",
}


def released_with_for(set_code, set_name, number, name=""):
    if "cracked ice" in (name or "").lower():       # the 8 Cracked Ice Holo basics = Terapagos ex UPC
        return "Terapagos ex Ultra-Premium Collection"
    try:
        n = int(re.match(r"\d+", str(number or "")).group())
    except Exception:
        n = None
    for (code, rng), label in RELEASED_WITH_BY_NUMBER.items():
        if code == set_code and n in rng:
            return label
    return nice_set_name(set_name)


def nice_set_name(name):
    """'SWSH09: Brilliant Stars' -> 'Brilliant Stars'; 'SM - Burning Shadows' -> 'Burning Shadows'."""
    n = re.sub(r"^(?:SWSH\d*|SV\d*|ME\d*|SM\d*|XY|BW)\s*[-:]\s*", "", name or "").strip()
    return n or name


def variant_for_energy(name, subtype):
    low = (name or "").lower()
    if "cosmo" in low:
        return "CH"
    if "cracked ice" in low:
        return "CI"
    if "tinsel" in low:
        return "TI"
    return SUBTYPE_MAP.get(subtype, "N")


def split_marker(name):
    """'Basic Grass Energy (Cosmos Holo)' -> ('Basic Grass Energy', '(Cosmos Holo)' ); strips ' - 009'."""
    n = re.sub(r"\s*-\s*\d+(/\d+)?\s*$", "", name or "").strip()
    m = re.search(r"(\s*\([^)]*\))\s*$", n)
    if m:
        return n[:m.start()].strip(), m.group(1).strip()
    return n, ""


def fmt_td(sec):
    return str(timedelta(seconds=int(max(sec, 0))))


class Command(BaseCommand):
    help = "Energy sets per era: import missing cards/variants, fix images, link, name with release set (dry run unless --apply)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--step", choices=STEPS, default="")
        parser.add_argument("--status", action="store_true")
        parser.add_argument("--rate", type=float)

    # -- helpers --------------------------------------------------------------
    def progress(self, step, i, total, text):
        line = f"[{step} {i}/{total}] {100 * i // max(total, 1):>3}%  {text}"
        self.stdout.write(line)
        if i % 10 == 0 or i == total:
            with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
                f.write(f"Energy build  {datetime.now():%Y-%m-%d %H:%M:%S}  ({'APPLY' if self.apply else 'DRY RUN'})\n{line}\n")

    def fetch_prices(self, gid):
        import requests
        if gid in self.price_cache:
            return self.price_cache[gid]
        out = {}
        try:
            r = requests.get(f"{TCGCSV_BASE}/{gid}/prices", headers=HEADERS, timeout=30)
            r.raise_for_status()
            for row in r.json().get("results", []):
                usd = row.get("marketPrice") or row.get("midPrice") or row.get("lowPrice")
                out[(str(row["productId"]), row.get("subTypeName") or "")] = usd
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"  prices for group {gid} failed: {str(e)[:80]} (new rows get TBC)"))
        self.price_cache[gid] = out
        time.sleep(0.1)
        return out

    def zar(self, usd):
        return _zar_price(usd, self.rate) if usd else Decimal("0")   # no price -> 0 = "TBC" (site-wide rule)

    def energy_rows(self):
        out = []
        for p in (PokemonProduct.objects.filter(condition="NM", name__icontains="energy")
                  .select_related("card_set", "card_set__era")):
            if energy_kind(p.name):
                out.append(p)
        return out

    # -- main -----------------------------------------------------------------
    def handle(self, *args, **o):
        if o["status"]:
            self.stdout.write(open(PROGRESS_FILE, encoding="utf-8").read() if os.path.exists(PROGRESS_FILE) else "No run yet.")
            return
        self.apply = o["apply"]
        self.price_cache = {}
        if not os.path.exists(CACHE_FILE):
            self.stdout.write(self.style.ERROR(f"{CACHE_FILE} not found -- run `python manage.py audit_energy` first."))
            return
        with open(CACHE_FILE, encoding="utf-8") as f:
            self.cache = json.load(f)
        self.rate = _get_rate(o.get("rate"))
        code_gid = {code: gid for code, (gid, _n, _e) in GROUP_CONFIG.items()}
        for code, gid in STANDALONE_ENERGY_GROUPS.items():
            code_gid.setdefault(code, gid)
        self.groups = sorted(code_gid.items())

        run = [o["step"]] if o["step"] else STEPS
        self.stdout.write(f"{'APPLY' if self.apply else 'DRY RUN'} -- steps: {', '.join(run)}\n")
        for step in run:
            connection.close()
            self.stdout.write(self.style.MIGRATE_HEADING(f"=== {step} ==="))
            getattr(self, f"step_{step}")()
        if not self.apply:
            self.stdout.write(self.style.WARNING("\nDry run -- nothing written. Add --apply to do it."))

    # 1 ---------------------------------------------------------------------
    def step_orphans(self):
        prizepack = CardSet.objects.filter(code="PRIZEPACK").first()
        orphans = [p for p in PokemonProduct.objects.filter(card_set__isnull=True, name__icontains="energy")
                   if energy_kind(p.name)]
        fixable = []
        for p in orphans:
            if p.tcgcsv_product_id and prizepack and PokemonProduct.objects.filter(
                    card_set=prizepack, tcgcsv_product_id=p.tcgcsv_product_id).exists():
                fixable.append(p)
        self.stdout.write(f"{len(orphans)} Energy row(s) with no set; {len(fixable)} belong to PRIZEPACK (a row with the same TCGplayer id is there).")
        for i, p in enumerate(fixable, 1):
            self.progress("orphans", i, len(fixable), f"{p.name} ({p.variant_override or 'N'}) -> PRIZEPACK")
            if self.apply:
                p.card_set = prizepack
                p.save(update_fields=["card_set"])
        left = len(orphans) - len(fixable)
        if left:
            self.stdout.write(f"{left} other no-set row(s) left alone (not Prize Pack energies).")

    # 2 ---------------------------------------------------------------------
    def step_sync(self):
        sets = {s.code: s for s in CardSet.objects.select_related("era")}
        by_pid = {}
        for p in PokemonProduct.objects.exclude(tcgcsv_product_id__isnull=True).filter(name__icontains="energy"):
            by_pid.setdefault(p.tcgcsv_product_id, []).append(p)
        tasks = []
        for code, gid in self.groups:
            home = sets.get(SET_ALIAS.get(code, code))
            for pid, info_ in self.cache.get(str(gid), {}).items():
                tasks.append((code, gid, home, int(pid), info_))
        total = len(tasks)
        created_cards = created_variants = skipped = 0
        category_fallback = None
        for i, (code, gid, home, pid, inf) in enumerate(tasks, 1):
            existing = by_pid.get(pid, [])
            have = {(p.variant_override or "N") for p in existing}
            subs = inf["subtypes"] or [""]
            want = {variant_for_energy(inf["name"], s): s for s in subs}
            missing = {v: s for v, s in want.items() if v not in have}
            # Cosmos / Cracked Ice / Tinsel products already on the site (often filed in another set and stored as
            # H) are the SAME card -- never add a second copy.
            if existing and re.search(r"cosmo|cracked ice|tinsel", inf["name"], re.I):
                missing = {}
            if not missing:
                continue
            if home is None:
                skipped += 1
                self.stdout.write(self.style.WARNING(f"  SKIP {inf['name']} ({pid}): set {code} is not on the site"))
                continue
            prices = self.fetch_prices(gid)
            for v, sub in missing.items():
                base = existing[0] if existing else None
                price = self.zar(prices.get((str(pid), sub)))
                kind = "variant" if base else "card"
                self.progress("sync", i, total, f"{kind:7} {home.code:6} {inf['name'][:38]:38} + {v}  {('R' + str(price)) if price else 'TBC'}")
                if kind == "card":
                    created_cards += 1
                else:
                    created_variants += 1
                if not self.apply:
                    continue
                with transaction.atomic():
                    num_m = re.match(r"\d+", str(inf.get("number") or ""))
                    row = PokemonProduct(
                        pb_id=f"TCGCSV-{pid}-{v}", tcgcsv_product_id=pid,
                        card_set=(base.card_set if base and base.card_set_id else home), variant_override=v,
                        variant_sort=PokemonProduct.VARIANT_SORT_ORDER.get(v, 9), condition="NM",
                        price=price, stock=0, is_active=True)
                    if base:
                        for f in ("name", "category", "rarity", "supertype", "card_number", "number", "description", "image_url"):
                            if hasattr(base, f):
                                setattr(row, f, getattr(base, f))
                    else:
                        row.name = clean(inf["name"]) if "(" not in inf["name"] else re.sub(r"\s*-\s*\d+$", "", inf["name"])
                        row.rarity = "common"
                        row.supertype = "Energy"
                        row.card_number = int(num_m.group()) if num_m else None
                        if category_fallback is None:
                            category_fallback = (PokemonProduct.objects.filter(card_set=home).exclude(category=None).values_list("category", flat=True).first()
                                                 or PokemonProduct.objects.exclude(category=None).values_list("category", flat=True).first())
                        row.category_id = category_fallback
                    row.save()
                    # own image on R2 (key includes the variant)
                    for size in ("400w", "200w"):
                        try:
                            url = info.rehost_card_image(row, info.tcgplayer_image(pid, size))
                        except Exception:
                            url = ""
                        if url:
                            PokemonProduct.objects.filter(pk=row.pk).update(image_url=url)
                            break
                    by_pid.setdefault(pid, []).append(row)
                time.sleep(0.05)
        self.stdout.write(f"\nNew cards: {created_cards} | new variants: {created_variants} | skipped: {skipped}")

    # 3 ---------------------------------------------------------------------
    def step_images(self):
        bad = [p for p in self.energy_rows() if p.image_url and not p.image_url.startswith(R2_PREFIX)]
        none = [p for p in self.energy_rows() if not p.image_url]
        self.stdout.write(f"{len(bad)} Energy image(s) not on R2; {len(none)} with no image.")
        todo = bad + none
        ok = failed = 0
        for i, p in enumerate(todo, 1):
            self.progress("images", i, len(todo), f"{p.card_set.code if p.card_set else '-':8} {p.name[:40]}")
            if not self.apply:
                continue
            urls = [p.image_url] if p.image_url else []
            if p.tcgcsv_product_id:
                urls += [info.tcgplayer_image(p.tcgcsv_product_id, "400w"), info.tcgplayer_image(p.tcgcsv_product_id, "200w")]
            new, why = "", []
            for u in urls:
                try:
                    new = info.rehost_card_image(p, u)
                    if not new:
                        why.append(f"no image at {u[-48:]}")
                except Exception as e:
                    new = ""
                    why.append(f"{type(e).__name__}: {str(e)[:70]}")
                if new:
                    break
            if new:
                PokemonProduct.objects.filter(pk=p.pk).update(image_url=new)
                ok += 1
            else:
                failed += 1
                self.stdout.write(self.style.WARNING(f"    FAILED pid={p.tcgcsv_product_id} {' | '.join(why)}"))
            time.sleep(0.05)
        if self.apply:
            self.stdout.write(f"Re-hosted {ok}; could not get an image for {failed}.")
            left = [p for p in self.energy_rows() if not p.image_url or not p.image_url.startswith(R2_PREFIX)]
            import csv
            with open("energy_missing_images.csv", "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["set", "name", "variant", "tcgcsv_product_id", "current_image_url"])
                for p in left:
                    w.writerow([p.card_set.code if p.card_set else "", p.name, p.variant_override or "N", p.tcgcsv_product_id or "", p.image_url or ""])
            self.stdout.write(f"{len(left)} Energy card(s) still without an R2 image -> energy_missing_images.csv")

    # 3b --------------------------------------------------------------------
    def step_fillgaps(self):
        """Energy cards TCGplayer has no picture for (SM Trainer Kit Energies): borrow the standard SM basic Energy
        art of the same type and stamp a ribbon on it ("TRAINER KIT #28") so it is clearly not the plain card.
        The result is its own R2 file. Dead external links are cleared."""
        import io
        import requests
        from products.admin import _r2_client, R2_BUCKET, R2_CDN
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            self.stdout.write(self.style.ERROR("Pillow missing -- run: pip install pillow"))
            return
        energy = self.energy_rows()
        gaps = [p for p in energy if not (p.image_url or "").startswith(R2_PREFIX)]
        donors = {}
        for p in energy:
            if (p.card_set and p.card_set.era and p.card_set.era.code == "SM" and not p.card_set.code.startswith("SMK")
                    and (p.variant_override or "N") == "N" and (p.image_url or "").startswith(R2_PREFIX)):
                stem = clean(p.name).lower()
                cur = donors.get(stem)
                if cur is None or (p.card_set.code in ("SM01", "SM1") and cur.card_set.code not in ("SM01", "SM1")):
                    donors[stem] = p
        self.stdout.write(f"{len(gaps)} card(s) without an R2 image; {len(donors)} donor Energy types found in the SM era.")
        done = failed = 0
        for i, p in enumerate(gaps, 1):
            word = clean(p.name).split(" ")[0].lower()
            donor = donors.get(f"{word} energy")
            m = re.search(r"#?(\d+)\)?\s*$", p.name)
            label = f"TRAINER KIT #{m.group(1)}" if m and p.name.rstrip().endswith(")") else "TRAINER KIT"
            if not donor:
                failed += 1
                self.progress("fillgaps", i, len(gaps), f"NO DONOR for {p.name}")
                continue
            self.progress("fillgaps", i, len(gaps), f"{p.card_set.code:6} {p.name[:30]:30} <- {donor.card_set.code} {donor.name[:28]}  [{label}]")
            if not self.apply:
                continue
            try:
                r = requests.get(donor.image_url, timeout=30)
                r.raise_for_status()
                im = Image.open(io.BytesIO(r.content)).convert("RGB")
                w, h = im.size
                bar_h = max(int(h * 0.09), 18)
                ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
                d = ImageDraw.Draw(ov)
                d.rectangle([0, h - bar_h, w, h], fill=(214, 40, 40, 235))
                font = None
                for fname in ("arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf"):
                    try:
                        font = ImageFont.truetype(fname, max(int(bar_h * 0.6), 10))
                        break
                    except Exception:
                        continue
                font = font or ImageFont.load_default()
                tw = d.textlength(label, font=font)
                d.text(((w - tw) / 2, h - bar_h + bar_h * 0.18), label, fill=(255, 255, 255, 255), font=font)
                out = Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")
                buf = io.BytesIO()
                out.save(buf, "JPEG", quality=88)
                key = f"cards/{p.card_set.code.lower()}_{p.tcgcsv_product_id or p.pk}_n.jpg"
                _r2_client().put_object(Bucket=R2_BUCKET, Key=key, Body=buf.getvalue(), ContentType="image/jpeg")
                PokemonProduct.objects.filter(pk=p.pk).update(image_url=f"{R2_CDN}/{key}")
                done += 1
            except Exception as e:
                failed += 1
                self.stdout.write(self.style.WARNING(f"    FAILED {p.name}: {type(e).__name__}: {str(e)[:80]}"))
            time.sleep(0.05)
        if self.apply:
            self.stdout.write(f"Stamped + uploaded {done}; failed {failed}.")

    # 4 ---------------------------------------------------------------------
    def step_eraset(self):
        eras = {e.code: e for e in Era.objects.all()}
        energy = self.energy_rows()
        by_era = {}
        for p in energy:
            if p.card_set and p.card_set.era:
                by_era.setdefault(p.card_set.era.code, []).append(p)
        total = len(ERA_ENERGY_SETS)
        for i, (era_code, (set_code, set_name)) in enumerate(ERA_ENERGY_SETS.items(), 1):
            era = eras.get(era_code)
            if not era:
                self.stdout.write(self.style.WARNING(f"  era {era_code} not found -- skipped"))
                continue
            members = [p for p in by_era.get(era_code, []) if p.card_set.code != set_code]
            self.progress("eraset", i, total, f"{set_code:7} {set_name:32} <- {len(members)} Energy card(s) from {era_code}")
            if not self.apply:
                continue
            es, _ = CardSet.objects.get_or_create(code=set_code, defaults={"name": set_name, "era": era})
            if es.era_id != era.id:
                es.era = era
                es.save(update_fields=["era"])
            # Lists sort by release date (undated sets sink to the bottom) and show a logo: give the Energy set the
            # era's newest set date so it sits with its era, and the era's own (R2) logo/symbol.
            dates = [d for d in CardSet.objects.filter(era=era).exclude(code__in=[c for c, _n in ERA_ENERGY_SETS.values()])
                     .exclude(release_date__isnull=True).values_list("release_date", flat=True)]
            upd = []
            if not es.release_date and dates:
                es.release_date = max(dates)
                upd.append("release_date")
            if not es.logo_url and getattr(era, "logo_url", ""):
                es.logo_url = era.logo_url
                upd.append("logo_url")
            if not es.symbol_url and getattr(era, "symbol_url", ""):
                es.symbol_url = era.symbol_url
                upd.append("symbol_url")
            if upd:
                es.save(update_fields=upd)
            for p in members:
                p.also_in_sets.add(es)
            es.total_cards = len({(p.tcgcsv_product_id or p.pk) for p in members} | {(p.tcgcsv_product_id or p.pk) for p in energy if p.card_set and p.card_set.code == set_code})
            es.save(update_fields=["total_cards"])

    # 5 ---------------------------------------------------------------------
    def step_names(self):
        energy = self.energy_rows()
        energy_set_codes = {c for c, _n in ERA_ENERGY_SETS.values()}
        log, changes = [], []
        for p in energy:
            sc = p.card_set
            if not sc:
                continue
            core, marker = split_marker(p.name)
            core = re.sub(r"\s*-\s*\d+(/\d+)?\s*$", "", core).strip()     # drop a left-over "- 012"
            rel = released_with_for(sc.code, sc.name, p.card_number, p.name)
            has_num = bool(re.search(r"-\s*\d+(/\d+)?", p.name))
            if not rel or (rel.lower() in p.name.lower() and not has_num):
                continue
            if sc.code == "PRIZEPACK" and "prize pack" in p.name.lower():
                continue
            if rel.lower() in marker.lower():                              # release set already in the name
                new = f"{core} {marker}"
            else:
                new = f"{core} ({rel})" + (f" {marker}" if marker else "")
            if new != p.name:
                changes.append((p, new))
        self.stdout.write(f"{len(changes)} of {len(energy)} Energy names will get their release set.")
        for i, (p, new) in enumerate(changes, 1):
            self.progress("names", i, len(changes), f"{p.name[:34]:34} -> {new[:60]}")
            log.append({"pk": p.pk, "old": p.name, "new": new})
            if self.apply:
                PokemonProduct.objects.filter(pk=p.pk).update(name=new)
        if self.apply and log:
            old = []
            if os.path.exists(RENAME_LOG):
                try:
                    old = json.load(open(RENAME_LOG, encoding="utf-8"))
                except Exception:
                    old = []
            with open(RENAME_LOG, "w", encoding="utf-8") as f:
                json.dump(old + log, f, indent=1)
            self.stdout.write(f"Old names saved in {RENAME_LOG}.")
