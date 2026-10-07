"""
enrich_serebii.py - PokeBulk SA

Serebii.net card database as an enrichment source (Michael, 2026-10-07: "add
Serebii as a source for all enrichment too ... concentrate on Mega Era").

FILL-ONLY: only writes a field that is currently blank, so it never
overwrites pokemontcg.io / Bulbapedia data. Run it AFTER those two.
NEVER touches price, stock, variant, image_url, card_number, name.

Page: https://www.serebii.net/card/<slug>/<NNN>.shtml  (NNN = card number,
zero padded to 3; secret rares continue past the set total).

Serebii draws energy symbols as images, so the parser turns <img> tags whose
filename names an energy type into [E:Type] tokens, and <b>/<strong> into
markers, before reading the text. THE PAGE LAYOUT WAS NOT VERIFIED AGAINST
RAW HTML when this was written -- always run --verify-only first and check the
printed parse for a few cards (an ex, a Basic, a Trainer) before a real run.

  python manage.py enrich_serebii MEG --verify-only
  python manage.py enrich_serebii MEG PFL ASC POR CRI BLK WHT PBL 30C --dry-run
  python manage.py enrich_serebii MEG PFL ASC POR CRI BLK WHT PBL 30C
"""
import re
import time

import requests
from django.core.management.base import BaseCommand
from django.db import transaction

from products.models import PokemonProduct, CardSet, PokemonType

BASE = "https://www.serebii.net/card"
HEADERS = {"User-Agent": "PokeBulkSA/1.0 (pokebulk.co.za)"}

# DB set code -> Serebii URL slug (English sets)
SEREBII_SLUGS = {
    "MEG": "megaevolution", "PFL": "phantasmalflames", "ASC": "ascendedheroes",
    "POR": "perfectorder", "CRI": "chaosrising", "PBL": "pitchblack",
    "BLK": "blackbolt", "WHT": "whiteflare", "30C": "30thcelebration",
    # Scarlet & Violet
    "SVI": "scarletviolet", "PAL": "paldeaevolved", "OBF": "obsidianflames",
    "MEW": "151", "PAR": "paradoxrift", "PAF": "paldeanfates",
    "TEF": "temporalforces", "TWM": "twilightmasquerade", "SFA": "shroudedfable",
    "SCR": "stellarcrown", "SSP": "surgingsparks", "PRE": "prismaticevolutions",
    "JTG": "journeytogether", "DRI": "destinedrivals",
}

ENERGY_NAMES = {
    "grass": "Grass", "fire": "Fire", "water": "Water", "lightning": "Lightning",
    "electric": "Lightning", "psychic": "Psychic", "fighting": "Fighting",
    "darkness": "Darkness", "dark": "Darkness", "metal": "Metal", "steel": "Metal",
    "fairy": "Fairy", "dragon": "Dragon", "colorless": "Colorless", "colourless": "Colorless",
}

FIELDS = [
    "hp", "artist", "weakness_type", "weakness_value", "resistance_type",
    "resistance_value", "retreat_cost",
    "ability_name", "ability_text",
    "attack_1_name", "attack_1_damage", "attack_1_text", "attack_1_cost",
    "attack_2_name", "attack_2_damage", "attack_2_text", "attack_2_cost",
    "attack_3_name", "attack_3_damage", "attack_3_text", "attack_3_cost",
]


def energy_from_src(tag):
    m = re.search(r'(?:src|alt|title)="([^"]*)"', tag, re.I)
    if not m:
        return None
    stem = re.sub(r'\.\w+$', '', m.group(1).rsplit('/', 1)[-1]).lower()
    for key, canon in ENERGY_NAMES.items():
        if key in stem:
            return canon
    return None


def html_to_marked_text(html):
    """HTML -> text with [E:Type] energy tokens and «B»..«/B» bold markers."""
    html = re.sub(r'(?is)<(script|style).*?</\1>', ' ', html)

    def img(m):
        e = energy_from_src(m.group(0))
        return f" [E:{e}] " if e else " "
    html = re.sub(r'(?is)<img\b[^>]*>', img, html)
    html = re.sub(r'(?i)<\s*(b|strong)\b[^>]*>', ' «B»', html)
    html = re.sub(r'(?i)<\s*/\s*(b|strong)\s*>', '«/B» ', html)
    html = re.sub(r'(?i)<br\s*/?>', ' ', html)
    text = re.sub(r'<[^>]+>', ' ', html)
    text = (text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&#039;', "'")
            .replace('&quot;', '"').replace('&eacute;', 'é'))
    return re.sub(r'\s+', ' ', text)


def energies(chunk):
    return ",".join(re.findall(r'\[E:(\w+)\]', chunk or ""))


def parse_card(html):
    t = html_to_marked_text(html)
    out = {}

    m = re.search(r'«B»\s*(\d+)\s*HP\s*«/B»|(\d+)\s*HP', t)
    if m:
        out["hp"] = int(m.group(1) or m.group(2))
    else:
        out["hp"] = None
    # Everything from the HP marker to the artist line is the card body.
    start = m.end() if m else 0
    am = re.search(r'Illustration:\s*([^|«\[]+?)(?:\s{2,}|\s*$|\s+(?:«|\[))', t[start:] + ' ')
    body_end = start + am.start() if am else len(t)
    body = t[start:body_end]
    out["artist"] = am.group(1).strip() if am else ""

    # Weakness / Resistance / Retreat
    wm = re.search(r'Weakness\s*«/B»?\s*((?:\[E:\w+\]\s*)*)\s*(x\d+|\+\d+)?', body, re.I)
    rm = re.search(r'Resistance\s*«/B»?\s*((?:\[E:\w+\]\s*)*)\s*(-\d+)?', body, re.I)
    tm = re.search(r'Retreat Cost\s*«/B»?\s*((?:\[E:\w+\]\s*)*)', body, re.I)
    out["weakness_type"] = (energies(wm.group(1)) if wm else "")
    out["weakness_value"] = (wm.group(2) or "") if wm and out["weakness_type"] else ""
    out["resistance_type"] = (energies(rm.group(1)) if rm else "")
    out["resistance_value"] = (rm.group(2) or "") if rm and out["resistance_type"] else ""
    out["retreat_cost"] = len(re.findall(r'\[E:\w+\]', tm.group(1))) if tm else None

    # Attacks: [E:..]* «B»Name«/B» effect text «B»damage«/B»?
    # Stop before the Weakness block so its energy tokens aren't read as a cost.
    atk_zone = re.split(r'Weakness', body, 1, flags=re.I)[0]
    atk_re = re.compile(
        r'((?:\[E:\w+\]\s*)*)«B»\s*([^«]+?)\s*«/B»\s*(.*?)(?=(?:\[E:\w+\]\s*)*«B»|$)', re.S)
    attacks, ability = [], None
    for cost, name, rest in atk_re.findall(atk_zone):
        rest = rest.strip()
        dm = re.search(r'«B»\s*([\d+×x\-]+)\s*«/B»\s*$', rest + ' ')
        damage = ""
        # trailing damage is its own bold chunk; our lookahead already cut it
        # into the *next* match, so handle the "name is actually a number" case
        if re.fullmatch(r'[\d+×x\-]+', name.strip()) and attacks:
            attacks[-1]["damage"] = name.strip()
            continue
        text = re.sub(r'«/?B»', '', rest).strip()
        if not cost.strip() and name.strip().lower() in ("ability", "poké-power", "poké-body"):
            continue
        if not cost.strip():
            # no energy cost shown -> an Ability (name then its text)
            if ability is None:
                ability = {"name": name.strip(), "text": text}
            continue
        attacks.append({"name": name.strip(), "text": text, "damage": damage, "cost": energies(cost)})

    if ability:
        out["ability_name"], out["ability_text"] = ability["name"], ability["text"]
    for i in range(3):
        a = attacks[i] if len(attacks) > i else {}
        out[f"attack_{i+1}_name"] = a.get("name", "")
        out[f"attack_{i+1}_damage"] = a.get("damage", "")
        out[f"attack_{i+1}_text"] = a.get("text", "")
        out[f"attack_{i+1}_cost"] = a.get("cost", "")
    return out


def fetch(slug, number):
    url = f"{BASE}/{slug}/{int(number):03d}.shtml"
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
    except requests.RequestException as e:
        return None, str(e)
    if r.status_code != 200:
        return None, f"HTTP {r.status_code}"
    return r.content.decode("latin-1", errors="replace"), None


class Command(BaseCommand):
    help = "Fill blank card fields from Serebii.net (fill-only, never overwrites)."

    def add_arguments(self, parser):
        parser.add_argument("set_codes", nargs="+")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--verify-only", action="store_true",
                            help="Parse the first 3 cards of each set and print the result; change nothing.")
        parser.add_argument("--delay", type=float, default=0.5)

    def handle(self, *args, **o):
        codes = [c.upper() for c in o["set_codes"]]
        if codes == ["ALL"]:
            codes = list(SEREBII_SLUGS)
        total_filled = 0
        for code in codes:
            slug = SEREBII_SLUGS.get(code)
            if not slug:
                self.stdout.write(f"[{code}] no Serebii slug mapped - skipping")
                continue
            try:
                db_set = CardSet.objects.get(code=code)
            except CardSet.DoesNotExist:
                self.stdout.write(f"[{code}] not in DB - skipping")
                continue
            numbers = list(
                PokemonProduct.objects.filter(card_set=db_set, card_number__isnull=False)
                .values_list("card_number", flat=True).distinct().order_by("card_number"))
            if o["verify_only"]:
                numbers = numbers[:3]
            self.stdout.write(f"\n[{code}] {slug}: {len(numbers)} card numbers")

            to_update, filled, missing = [], 0, 0
            for n in numbers:
                html, err = fetch(slug, n)
                time.sleep(o["delay"])
                if not html:
                    missing += 1
                    if o["verify_only"]:
                        self.stdout.write(f"  #{n}: {err}")
                    continue
                parsed = parse_card(html)
                if o["verify_only"]:
                    self.stdout.write(f"  #{n}: " + ", ".join(
                        f"{k}={v!r}" for k, v in parsed.items() if v not in ("", None)))
                    continue
                for p in PokemonProduct.objects.filter(card_set=db_set, card_number=n):
                    changed = False
                    for f in FIELDS:
                        v = parsed.get(f)
                        if v in ("", None):
                            continue
                        if not getattr(p, f, None):
                            setattr(p, f, v)
                            changed = True
                    if changed:
                        to_update.append(p)
                        filled += 1
                if len(to_update) >= 100 and not o["dry_run"]:
                    with transaction.atomic():
                        PokemonProduct.objects.bulk_update(to_update, FIELDS, batch_size=200)
                    to_update = []
            if to_update and not o["dry_run"] and not o["verify_only"]:
                with transaction.atomic():
                    PokemonProduct.objects.bulk_update(to_update, FIELDS, batch_size=200)
            self.stdout.write(f"  rows filled: {filled} | pages not found: {missing}"
                              + (" (DRY RUN)" if o["dry_run"] else ""))
            total_filled += filled
        self.stdout.write(f"\nDONE - rows filled: {total_filled}")
