"""
Management command: download_card_images
========================================
Downloads hi-res card images organised by era folder.
Tries three sources in order:
  1. pokemontcg.io CDN  (primary — best quality)
  2. TCGdex CDN         (fallback — free, no key needed)
  3. Scrydex CDN        (tertiary fallback)

Filename: {SET}-{NUM}-{Name}-{Rarity}.png
Folder:   media/card_images/originals/{Era}/

Examples:
    WotC/BS-004-Charizard-Holo-Rare.png
    WotC/BS-058-Pikachu-Common.png
    MEG-Era/MEG-001-Venusaur-ex-Double-Rare.png
    MEG-Era/PFL-013-Mega-Charizard-X-ex-Double-Rare.png
    MEG-Era/ASC-001-Ericas-Oddish-Common.png
    SV-Era/SCR-001-Venusaur-ex-Double-Rare.png

Usage:
    python manage.py download_card_images
    python manage.py download_card_images --set ASC
    python manage.py download_card_images --force
    python manage.py download_card_images --dry-run
    python manage.py download_card_images --source tcgdex
"""

import os, json, time, random, re, requests
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from products.models import PokemonProduct

PROGRESS_FILE = "card_image_progress.json"
DELAY_MIN     = 1.2
DELAY_MAX     = 2.8
BURST_PAUSE   = 8.0
BURST_EVERY   = 25

HEADERS = {"User-Agent": "PokeBulkSA/1.0 (pokebulksa.co.za; card image archiver)"}
if getattr(settings, "POKEMONTCG_API_KEY", None):
    HEADERS["X-Api-Key"] = settings.POKEMONTCG_API_KEY

# ── Era folder map ────────────────────────────────────────────────────────────
ERA_MAP = {
    # WotC
    "BS":"WotC","JU":"WotC","FO":"WotC","B2":"WotC","TR":"WotC",
    "G1":"WotC","G2":"WotC","N1":"WotC","N2":"WotC","N3":"WotC","N4":"WotC",
    "LC":"WotC",
    # EX Era
    "RS":"EX-Era","SS":"EX-Era","DR":"EX-Era","MA":"EX-Era","HL":"EX-Era",
    "RG":"EX-Era","TRR":"EX-Era","DX":"EX-Era","EM":"EX-Era","UF":"EX-Era",
    "DS":"EX-Era","LM":"EX-Era","HP":"EX-Era","CG":"EX-Era","DF":"EX-Era",
    "PK":"EX-Era","TK1A":"EX-Era","TK1B":"EX-Era","TK2A":"EX-Era","TK2B":"EX-Era",
    # DP Era
    "DP":"DP-Era","MT":"DP-Era","SW":"DP-Era","GE":"DP-Era","MD":"DP-Era",
    "LA":"DP-Era","SF":"DP-Era","PL":"DP-Era","RR":"DP-Era","AR":"DP-Era",
    "HS":"DP-Era","UL":"DP-Era","UD":"DP-Era","TM":"DP-Era","CL":"DP-Era",
    # BW Era
    "BLW":"BW-Era","EPO":"BW-Era","NVI":"BW-Era","NXD":"BW-Era","DEX":"BW-Era",
    "DRX":"BW-Era","DRV":"BW-Era","BCR":"BW-Era","PLS":"BW-Era","PLF":"BW-Era",
    "PLB":"BW-Era","LTR":"BW-Era","DCR":"BW-Era",
    # XY Era
    "XY":"XY-Era","FLF":"XY-Era","FFI":"XY-Era","PHF":"XY-Era","PRC":"XY-Era",
    "ROS":"XY-Era","AOR":"XY-Era","BKT":"XY-Era","BKP":"XY-Era","FCO":"XY-Era",
    "STS":"XY-Era","EVO":"XY-Era","GEN":"XY-Era","PR-XY":"XY-Era",
    # SM Era
    "SUM":"SM-Era","GRI":"SM-Era","BUS":"SM-Era","SLG":"SM-Era","CIN":"SM-Era",
    "UPR":"SM-Era","FLI":"SM-Era","CES":"SM-Era","DRM":"SM-Era","LOT":"SM-Era",
    "TEU":"SM-Era","DET":"SM-Era","UNB":"SM-Era","UNM":"SM-Era","HIF":"SM-Era",
    "CEC":"SM-Era","PR-SM":"SM-Era",
    # SWSH Era
    "SSH":"SWSH-Era","RCL":"SWSH-Era","DAA":"SWSH-Era","CPA":"SWSH-Era",
    "VIV":"SWSH-Era","SHF":"SWSH-Era","BST":"SWSH-Era","CRE":"SWSH-Era",
    "EVS":"SWSH-Era","CEL":"SWSH-Era","FST":"SWSH-Era","BRS":"SWSH-Era",
    "ASR":"SWSH-Era","LOR":"SWSH-Era","SIT":"SWSH-Era","CRZ":"SWSH-Era",
    "PR-SW":"SWSH-Era",
    # SV Era
    "SV1":"SV-Era","SVI":"SV-Era","PAL":"SV-Era","OBF":"SV-Era","MEW":"SV-Era",
    "PAF":"SV-Era","TEF":"SV-Era","TWM":"SV-Era","SFA":"SV-Era","SCR":"SV-Era",
    "SSP":"SV-Era","PRE":"SV-Era","JTG":"SV-Era","PR-SV":"SV-Era","SVP":"SV-Era",
    # MEG Era
    "MEG":"MEG-Era","PFL":"MEG-Era","ASC":"MEG-Era","POR":"MEG-Era","CR":"MEG-Era",
}

# ── pokemontcg.io CDN codes ───────────────────────────────────────────────────
POKEMONTCGIO_MAP = {
    # WotC
    "BS":"base1","JU":"base2","FO":"base3","B2":"base4","TR":"base5",
    "G1":"gym1","G2":"gym2","N1":"neo1","N2":"neo2","N3":"neo3","N4":"neo4",
    "LC":"lc",
    # EX Era
    "RS":"ex1","SS":"ex2","DR":"ex3","MA":"ex4","HL":"ex5","RG":"ex6",
    "TRR":"ex7","DX":"ex8","EM":"ex9","UF":"ex10","DS":"ex11","LM":"ex12",
    "HP":"ex13","CG":"ex14","DF":"ex15","PK":"ex16",
    # DP Era
    "DP":"dp1","MT":"dp2","SW":"dp3","GE":"dp4","MD":"dp5","LA":"dp6","SF":"dp7",
    "PL":"pl1","RR":"pl2","SV":"pl3","AR":"pl4",
    "HS":"hgss1","UL":"hgss2","UD":"hgss3","TM":"hgss4","CL":"col1",
    # BW Era
    "BLW":"bw1","EPO":"bw2","NVI":"bw3","NXD":"bw4","DEX":"bw5","DRX":"bw6",
    "DRV":"dv1","BCR":"bw7","PLS":"bw8","PLF":"bw9","PLB":"bw10",
    "LTR":"bw11","DCR":"dc1",
    # XY Era
    "XY":"xy1","FLF":"xy2","FFI":"xy3","PHF":"xy4","PRC":"xy5","ROS":"xy6",
    "AOR":"xy7","BKT":"xy8","BKP":"xy9","FCO":"xy10","STS":"xy11","EVO":"xy12",
    "GEN":"g1","PR-XY":"xyp",
    # SM Era
    "SUM":"sm1","GRI":"sm2","BUS":"sm3","SLG":"sm35","CIN":"sm4","UPR":"sm5",
    "FLI":"sm6","CES":"sm7","DRM":"sm75","LOT":"sm8","TEU":"sm9","DET":"det1",
    "UNB":"sm10","UNM":"sm11","HIF":"sm115","CEC":"sm12","PR-SM":"smp",
    # SWSH Era
    "SSH":"swsh1","RCL":"swsh2","DAA":"swsh3","CPA":"swsh35","VIV":"swsh4",
    "SHF":"swsh45","BST":"swsh5","CRE":"swsh6","EVS":"swsh7","CEL":"swsh8",
    "FST":"swsh9","BRS":"swsh10","ASR":"swsh11","LOR":"swsh12","SIT":"swsh13",
    "CRZ":"swsh12pt5","PR-SW":"swshp",
    # SV Era — SVI and SV1 are the same set on pokemontcg.io
    "SV1":"sv1","SVI":"sv1","PAL":"sv2","OBF":"sv3","MEW":"sv3pt5",
    "PAF":"sv4pt5","TEF":"sv4","TWM":"sv6","SFA":"sv6pt5","SCR":"sv7",
    "SSP":"sv8","PRE":"sv8pt5","JTG":"sv9","PR-SV":"svp","SVP":"svp",
    # MEG Era
    "MEG":"me1","PFL":"me2","ASC":"me2pt5","POR":"me3",
    "CR":"me4",   # Chaos Rising — releases May 22 2026, add when live
}

# ── TCGdex fallback codes ─────────────────────────────────────────────────────
# Format: https://assets.tcgdex.net/en/{series}/{set}/{number}/high.png
TCGDEX_MAP = {
    "BS":("base","base1"),"JU":("base","base2"),"FO":("base","base3"),
    "B2":("base","base4"),"TR":("base","base5"),
    "G1":("gym","gym1"),"G2":("gym","gym2"),
    "N1":("neo","neo1"),"N2":("neo","neo2"),"N3":("neo","neo3"),"N4":("neo","neo4"),
    "LC":("ecard","lc"),
    "HS":("hgss","hgss1"),"UL":("hgss","hgss2"),"UD":("hgss","hgss3"),
    "TM":("hgss","hgss4"),"CL":("hgss","col1"),
    "BLW":("bw","bw1"),"EPO":("bw","bw2"),"NVI":("bw","bw3"),"NXD":("bw","bw4"),
    "DEX":("bw","bw5"),"DRX":("bw","bw6"),"BCR":("bw","bw7"),"PLS":("bw","bw8"),
    "PLF":("bw","bw9"),"PLB":("bw","bw10"),"LTR":("bw","bw11"),
    "XY":("xy","xy1"),"FLF":("xy","xy2"),"FFI":("xy","xy3"),"PHF":("xy","xy4"),
    "PRC":("xy","xy5"),"ROS":("xy","xy6"),"AOR":("xy","xy7"),"BKT":("xy","xy8"),
    "BKP":("xy","xy9"),"FCO":("xy","xy10"),"STS":("xy","xy11"),"EVO":("xy","xy12"),
    "SUM":("sm","sm1"),"GRI":("sm","sm2"),"BUS":("sm","sm3"),"CIN":("sm","sm4"),
    "UPR":("sm","sm5"),"FLI":("sm","sm6"),"CES":("sm","sm7"),"LOT":("sm","sm8"),
    "TEU":("sm","sm9"),"UNB":("sm","sm10"),"UNM":("sm","sm11"),"CEC":("sm","sm12"),
    "SSH":("swsh","swsh1"),"RCL":("swsh","swsh2"),"DAA":("swsh","swsh3"),
    "VIV":("swsh","swsh4"),"BST":("swsh","swsh5"),"CRE":("swsh","swsh6"),
    "EVS":("swsh","swsh7"),"CEL":("swsh","swsh8"),"FST":("swsh","swsh9"),
    "BRS":("swsh","swsh10"),"ASR":("swsh","swsh11"),"LOR":("swsh","swsh12"),
    "SIT":("swsh","swsh13"),"CRZ":("swsh","swsh12pt5"),
    "SV1":("sv","sv1"),"SVI":("sv","sv1"),"PAL":("sv","sv2"),"OBF":("sv","sv3"),
    "MEW":("sv","sv3pt5"),"TEF":("sv","sv4"),"TWM":("sv","sv6"),
    "SFA":("sv","sv6pt5"),"SCR":("sv","sv7"),"SSP":("sv","sv8"),
    "PRE":("sv","sv8pt5"),
    # MEG Era on TCGdex
    "MEG":("me","me1"),"PFL":("me","me2"),"ASC":("me","me2pt5"),
    "POR":("me","me3"),"CR":("me","me4"),
}

# ── Scrydex fallback codes ────────────────────────────────────────────────────
SCRYDEX_MAP = {
    "SV1":"sv1","SVI":"sv1","PAL":"sv2","OBF":"sv3","MEW":"sv3pt5",
    "TEF":"sv4","TWM":"sv6","SFA":"sv6pt5","SCR":"sv7","SSP":"sv8",
    "PRE":"sv8pt5","SSH":"swsh1","RCL":"swsh2","DAA":"swsh3","VIV":"swsh4",
    "BST":"swsh5","CRE":"swsh6","EVS":"swsh7","BRS":"swsh10","LOR":"swsh12",
    "MEG":"me1","PFL":"me2","ASC":"me2pt5","POR":"me3","CR":"me4",
}

# ── Rarity label cleaner ──────────────────────────────────────────────────────
RARITY_CLEAN = {
    "Common":                    "Common",
    "Uncommon":                  "Uncommon",
    "Rare":                      "Rare",
    "Rare Holo":                 "Holo-Rare",
    "Rare Holo EX":              "Holo-Rare-EX",
    "Rare Holo GX":              "Holo-Rare-GX",
    "Rare Holo V":               "Rare-V",
    "Rare Holo VMAX":            "Rare-VMAX",
    "Rare Holo VSTAR":           "Rare-VSTAR",
    "Double Rare":               "Double-Rare",
    "Illustration Rare":         "Illustration-Rare",
    "Ultra Rare":                "Ultra-Rare",
    "Special Illustration Rare": "Special-Illustration-Rare",
    "Hyper Rare":                "Hyper-Rare",
    "Rare Secret":               "Secret-Rare",
    "Rare Rainbow":              "Rainbow-Rare",
    "Rare Shining":              "Shining-Rare",
    "Rare Shiny":                "Shiny-Rare",
    "Rare Shiny GX":             "Shiny-Rare-GX",
    "Rare BREAK":                "BREAK-Rare",
    "LEGEND":                    "Legend",
    "Promo":                     "Promo",
    "Mega Attack Rare":          "Mega-Attack-Rare",
    "Mega Hyper Rare":           "Mega-Hyper-Rare",
    "Amazing Rare":              "Amazing-Rare",
    "Radiant Rare":              "Radiant-Rare",
    "ACE SPEC Rare":             "ACE-SPEC",
}


# DB stores rarities as lowercase_underscore — map to clean labels
RARITY_DB_MAP = {
    "common":                       "Common",
    "uncommon":                     "Uncommon",
    "rare":                         "Rare",
    "rare_holo":                    "Holo-Rare",
    "holo_rare":                    "Holo-Rare",
    "rare holo":                    "Holo-Rare",
    "rare_holo_ex":                 "Holo-Rare-EX",
    "rare_holo_gx":                 "Holo-Rare-GX",
    "rare_holo_v":                  "Rare-V",
    "rare_holo_vmax":               "Rare-VMAX",
    "rare_holo_vstar":              "Rare-VSTAR",
    "double_rare":                  "Double-Rare",
    "illustration_rare":            "Illustration-Rare",
    "ultra_rare":                   "Ultra-Rare",
    "special_illustration_rare":    "Special-Illustration-Rare",
    "hyper_rare":                   "Hyper-Rare",
    "rare_secret":                  "Secret-Rare",
    "rare_rainbow":                 "Rainbow-Rare",
    "rare_shining":                 "Shining-Rare",
    "rare_shiny":                   "Shiny-Rare",
    "rare_shiny_gx":                "Shiny-Rare-GX",
    "rare_break":                   "BREAK-Rare",
    "legend":                       "Legend",
    "promo":                        "Promo",
    "mega_attack_rare":             "Mega-Attack-Rare",
    "mega_hyper_rare":              "Mega-Hyper-Rare",
    "amazing_rare":                 "Amazing-Rare",
    "radiant_rare":                 "Radiant-Rare",
    "ace_spec_rare":                "ACE-SPEC",
    "trainer_gallery_rare_holo":    "Trainer-Gallery-Holo",
    "classic_collection":           "Classic-Collection",
}


def clean_rarity(rarity):
    """Return a filename-safe rarity label from DB rarity value."""
    if not rarity:
        return ""
    # Normalise: lowercase, replace spaces with underscores
    key = rarity.strip().lower().replace(" ", "_")
    if key in RARITY_DB_MAP:
        return RARITY_DB_MAP[key]
    # Fallback: title-case with hyphens
    return rarity.strip().replace("_", " ").title().replace(" ", "-")


# Variant suffixes stored in product names — strip these for the base filename
# Format in DB: 'Oddish (Reverse Holo)', 'Pikachu (Normal)', 'Charizard (Holofoil)'
VARIANT_NAME_PATTERNS = [
    r"\s*\(Reverse Holo\)$",
    r"\s*\(Normal\)$",
    r"\s*\(Holofoil\)$",
    r"\s*\(Holo\)$",
    r"\s*\(1st Edition\)$",
    r"\s*\(First Edition\)$",
    r"\s*\(Mirror Holo\)$",
    r"\s*\(ETB Reverse Holo\)$",
    r"\s*\(Ace Spec\)$",
    r"\s*\(Poké Ball Holo\)$",
    r"\s*\(Master Ball Holo\)$",
    r"\s*\(Fast Ball Holo\)$",
    r"\s*\(Luxury Ball Holo\)$",
    r"\s*\(Quick Ball Holo\)$",
    r"\s*\(Dusk Ball Holo\)$",
    r"\s*\(Rocket Ball Holo\)$",
    r"\s*\(Love Ball Holo\)$",
    r"\s*\(Friend Ball Holo\)$",
    r"\s*\(Energy Holo\)$",
    # Generic fallback — anything in parentheses at the end
    r"\s*\([^)]+\)$",
]


def clean_card_name(name):
    """Strip variant suffixes in parentheses from a product name."""
    if not name:
        return "Unknown"
    cleaned = name.strip()
    for pattern in VARIANT_NAME_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()
        if "(" not in cleaned:
            break
    return cleaned.strip() or "Unknown"


def get_era(sc):
    return ERA_MAP.get(sc.upper(), "Other")


def make_filename(set_code, card_number, card_name, rarity, variant=None):
    """
    Build descriptive filename:
      {SET}-{NUM_PADDED}-{Name}-{Rarity}.png
      {SET}-{NUM_PADDED}-{Name}-{Rarity}-{VARIANT}.png  (variants folder)
    """
    # Zero-pad number to 3 digits; keep alphanumeric as-is (TG01, GG01 etc)
    try:
        padded = str(int(card_number)).zfill(3)
    except (ValueError, TypeError):
        padded = str(card_number)

    # Sanitise name
    safe_name = re.sub(r"[^\w\s-]", "", card_name or "Unknown")
    safe_name = re.sub(r"\s+", "-", safe_name.strip())
    safe_name = re.sub(r"-+", "-", safe_name).strip("-")

    # Rarity suffix
    rarity_suffix = clean_rarity(rarity)

    parts = [set_code, padded, safe_name]
    if rarity_suffix:
        parts.append(rarity_suffix)
    if variant:
        parts.append(variant.replace("/", "-").replace("\\", "-"))

    return "-".join(parts) + ".png"


class Command(BaseCommand):
    help = "Download hi-res card images organised by era (3-source fallback)"

    def add_arguments(self, parser):
        parser.add_argument("--set",       dest="set_code",
                            help="Only download this set (e.g. ASC, MEG, SCR)")
        parser.add_argument("--force",     action="store_true",
                            help="Re-download images that already exist")
        parser.add_argument("--dry-run",   action="store_true",
                            help="Preview without downloading")
        parser.add_argument("--delay-min", type=float, default=DELAY_MIN)
        parser.add_argument("--delay-max", type=float, default=DELAY_MAX)
        parser.add_argument("--source",
                            choices=["auto","pokemontcgio","tcgdex","scrydex"],
                            default="auto",
                            help="Force a specific image source")

    def handle(self, *args, **options):
        set_filter   = options["set_code"]
        force        = options["force"]
        dry_run      = options["dry_run"]
        dmin         = options["delay_min"]
        dmax         = options["delay_max"]
        src_override = options["source"]

        base_dir = Path(settings.MEDIA_ROOT) / "card_images" / "originals"
        base_dir.mkdir(parents=True, exist_ok=True)

        progress = self._load_progress()

        # Pull one row per unique (set_code, card_number) — first name & rarity seen
        qs = PokemonProduct.objects.select_related("card_set").values(
            "card_set__code", "card_number", "name", "rarity"
        ).distinct()
        if set_filter:
            qs = qs.filter(card_set__code=set_filter)

        # Deduplicate: one image per (set_code, card_number)
        # Use clean_card_name to strip variant suffixes like (Reverse Holo), (Normal) etc
        work = {}
        for row in qs:
            sc     = row["card_set__code"]
            num    = row["card_number"]
            name   = clean_card_name(row["name"] or "")
            rarity = row["rarity"] or ""
            if sc and num:
                key = f"{sc}:{num}"
                if key not in work:
                    work[key] = (sc, num, name, rarity)

        total, done, skipped, failed, no_source = len(work), 0, 0, [], []

        self.stdout.write(self.style.HTTP_INFO(
            f"\n{'[DRY RUN] ' if dry_run else ''}"
            f"Queued {total} unique card images  "
            f"(source={src_override})\n"
        ))

        for i, (key, (sc, num, name, rarity)) in enumerate(work.items(), 1):
            era      = get_era(sc)
            filename = make_filename(sc, num, name, rarity)
            dest_dir  = base_dir / era / sc   # era/SET/filename.png
            dest_file = dest_dir / filename

            if key in progress.get("completed", set()) and not force:
                skipped += 1
                continue

            if dest_file.exists() and not force:
                progress.setdefault("completed", set()).add(key)
                skipped += 1
                continue

            if dry_run:
                sources = self._available_sources(sc)
                self.stdout.write(
                    f"  [DRY] {era}/{filename}"
                    f"  [sources: {', '.join(sources) if sources else 'none'}]"
                )
                done += 1
                continue

            url, source_used = self._find_image(sc, num, src_override)

            if not url:
                self.stdout.write(self.style.WARNING(
                    f"  ✗ [{i}/{total}] No image: {era}/{filename}"
                ))
                failed.append(f"{sc}/{num}")
                time.sleep(random.uniform(dmin, dmax))
                continue

            if self._download(url, dest_dir, dest_file):
                done += 1
                progress.setdefault("completed", set()).add(key)
                self.stdout.write(
                    f"  ✓ [{i}/{total}] {era}/{filename}  [{source_used}]"
                )
            else:
                failed.append(f"{sc}/{num}")
                self.stdout.write(self.style.WARNING(
                    f"  ✗ [{i}/{total}] Download failed: {era}/{filename}"
                ))

            if i % BURST_EVERY == 0:
                self.stdout.write(self.style.HTTP_INFO(
                    f"  ⏸  Burst pause {BURST_PAUSE}s…"
                ))
                time.sleep(BURST_PAUSE)
            else:
                time.sleep(random.uniform(dmin, dmax))

            if i % 10 == 0:
                self._save_progress(progress)

        self._save_progress(progress)

        self.stdout.write("\n" + "─" * 50)
        self.stdout.write(self.style.SUCCESS(f"  Downloaded  : {done}"))
        self.stdout.write(self.style.HTTP_INFO(f"  Skipped     : {skipped}  (already on disk)"))
        if failed:
            self.stdout.write(self.style.ERROR(f"  Failed      : {len(failed)}"))
            for f in failed[:20]:
                self.stdout.write(f"    - {f}")
            if len(failed) > 20:
                self.stdout.write(f"    ... +{len(failed)-20} more")
        self.stdout.write("─" * 50 + "\n")

    # ── Source resolution ─────────────────────────────────────────────────────

    def _available_sources(self, sc):
        sources = []
        if POKEMONTCGIO_MAP.get(sc.upper()):
            sources.append("pokemontcgio")
        if sc.upper() in TCGDEX_MAP:
            sources.append("tcgdex")
        if sc.upper() in SCRYDEX_MAP:
            sources.append("scrydex")
        return sources

    def _find_image(self, sc, num, src_override="auto"):
        if src_override != "auto":
            url = self._try_source(src_override, sc, num)
            return (url, src_override) if url else (None, None)
        for source in ["pokemontcgio", "tcgdex", "scrydex"]:
            url = self._try_source(source, sc, num)
            if url:
                return url, source
        return None, None

    def _try_source(self, source, sc, num):
        sc_upper = sc.upper()

        if source == "pokemontcgio":
            code = POKEMONTCGIO_MAP.get(sc_upper)
            if not code:
                return None
            cdn = f"https://images.pokemontcg.io/{code}/{num}_hires.png"
            try:
                r = requests.head(cdn, headers=HEADERS, timeout=10)
                if r.status_code == 200:
                    return cdn
            except requests.RequestException:
                pass
            try:
                r = requests.get(
                    f"https://api.pokemontcg.io/v2/cards/{code}-{num}",
                    headers=HEADERS, timeout=15
                )
                if r.status_code == 200:
                    d = r.json().get("data", {})
                    return (d.get("images", {}).get("large") or
                            d.get("images", {}).get("small"))
            except requests.RequestException:
                pass
            return None

        elif source == "tcgdex":
            entry = TCGDEX_MAP.get(sc_upper)
            if not entry:
                return None
            series, set_code = entry
            url = f"https://assets.tcgdex.net/en/{series}/{set_code}/{num}/high.png"
            try:
                r = requests.head(url, timeout=10)
                if r.status_code == 200:
                    return url
            except requests.RequestException:
                pass
            return None

        elif source == "scrydex":
            code = SCRYDEX_MAP.get(sc_upper)
            if not code:
                return None
            url = f"https://images.scrydex.com/pokemon/{code}-{num}/large"
            try:
                r = requests.head(url, timeout=10)
                if r.status_code == 200:
                    return url
            except requests.RequestException:
                pass
            return None

        return None

    def _download(self, url, dest_dir, dest_file):
        dest_dir.mkdir(parents=True, exist_ok=True)
        try:
            r = requests.get(url, headers=HEADERS, timeout=30, stream=True)
            if r.status_code == 200:
                with open(dest_file, "wb") as fh:
                    for chunk in r.iter_content(8192):
                        fh.write(chunk)
                return True
        except requests.RequestException:
            pass
        return False

    def _load_progress(self):
        if os.path.exists(PROGRESS_FILE):
            try:
                with open(PROGRESS_FILE) as fh:
                    d = json.load(fh)
                    d["completed"] = set(d.get("completed", []))
                    return d
            except Exception:
                pass
        return {"completed": set()}

    def _save_progress(self, p):
        d = dict(p)
        d["completed"] = list(p.get("completed", set()))
        with open(PROGRESS_FILE, "w") as fh:
            json.dump(d, fh, indent=2)
