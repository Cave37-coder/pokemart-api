"""
Run from your project root to patch download_card_images with the full
pokemontcg.io set code mapping table.

    cd C:\\Users\\texca\\pokemart-api
    python patch_image_command.py
"""

import os

PATH = os.path.join("products", "management", "commands", "download_card_images.py")

CONTENT = '''"""
Management command: download_card_images
========================================
Downloads hi-res card images from pokemontcg.io for every PokemonProduct
in the database. Saves one clean image per unique (set_code, card_number).

Usage:
    python manage.py download_card_images
    python manage.py download_card_images --set sv3pt5
    python manage.py download_card_images --force
    python manage.py download_card_images --dry-run

Output:
    media/card_images/originals/{set_code}/{card_number}.png

Progress saved to card_image_progress.json  (add to .gitignore)
"""

import os, json, time, random, requests
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from products.models import PokemonProduct

PROGRESS_FILE  = "card_image_progress.json"
IMAGES_CDN     = "https://images.pokemontcg.io"
POKEMONTCG_API = "https://api.pokemontcg.io/v2/cards"

DELAY_MIN   = 1.2
DELAY_MAX   = 2.8
BURST_PAUSE = 8.0
BURST_EVERY = 25

HEADERS = {"User-Agent": "PokeBulkSA/1.0 (pokebulksa.co.za; card image archiver)"}
if hasattr(settings, "POKEMONTCG_API_KEY") and settings.POKEMONTCG_API_KEY:
    HEADERS["X-Api-Key"] = settings.POKEMONTCG_API_KEY

# ── Your internal code → pokemontcg.io CDN code ─────────────────────────────
# pokemontcg.io uses lowercase codes; mapping is case-insensitive on lookup.
SET_CODE_MAP = {
    # WotC Original
    "BS":    "base1",
    "JU":    "base2",
    "FO":    "base3",
    "B2":    "base4",
    "TR":    "base5",
    # Gym
    "G1":    "gym1",
    "G2":    "gym2",
    # Neo
    "N1":    "neo1",
    "N2":    "neo2",
    "N3":    "neo3",
    "N4":    "neo4",
    # e-Series
    "LC":    "lc",
    "EX":    "expedition",
    "AQ":    "aquapolis",
    "SK":    "skyridge",
    # EX Era (Ruby & Sapphire onwards)
    "RS":    "ex1",
    "SS":    "ex2",
    "DR":    "ex3",
    "MA":    "ex4",
    "HL":    "ex5",
    "RG":    "ex6",
    "TRR":   "ex7",
    "DX":    "ex8",
    "EM":    "ex9",
    "UF":    "ex10",
    "DS":    "ex11",
    "LM":    "ex12",
    "HP":    "ex13",
    "CG":    "ex14",
    "DF":    "ex15",
    "PK":    "ex16",
    # Diamond & Pearl
    "DP":    "dp1",
    "MT":    "dp2",
    "SW":    "dp3",
    "GE":    "dp4",
    "MD":    "dp5",
    "LA":    "dp6",
    "SF":    "dp7",
    # Platinum
    "PL":    "pl1",
    "RR":    "pl2",
    "SV":    "pl3",
    "AR":    "pl4",
    # HeartGold & SoulSilver
    "HS":    "hgss1",
    "UL":    "hgss2",
    "UD":    "hgss3",
    "TM":    "hgss4",
    "CL":    "col1",
    # Black & White
    "BLW":   "bw1",
    "EPO":   "bw2",
    "NVI":   "bw3",
    "NXD":   "bw4",
    "DEX":   "bw5",
    "DRX":   "bw6",
    "DRV":   "dv1",
    "BCR":   "bw7",
    "PLS":   "bw8",
    "PLF":   "bw9",
    "PLB":   "bw10",
    "LTR":   "bw11",
    "DCR":   "dc1",
    # XY
    "XY":    "xy1",
    "FLF":   "xy2",
    "FFI":   "xy3",
    "PHF":   "xy4",
    "PRC":   "xy5",
    "ROS":   "xy6",
    "AOR":   "xy7",
    "BKT":   "xy8",
    "BKP":   "xy9",
    "FCO":   "xy10",
    "STS":   "xy11",
    "EVO":   "xy12",
    "GEN":   "g1",
    "PR-XY": "xyp",
    # Sun & Moon
    "SUM":   "sm1",
    "GRI":   "sm2",
    "BUS":   "sm3",
    "SLG":   "sm35",
    "CIN":   "sm4",
    "UPR":   "sm5",
    "FLI":   "sm6",
    "CES":   "sm7",
    "DRM":   "sm75",
    "LOT":   "sm8",
    "TEU":   "sm9",
    "DET":   "det1",
    "UNB":   "sm10",
    "UNM":   "sm11",
    "HIF":   "sm115",
    "CEC":   "sm12",
    "PR-SM": "smp",
    # Sword & Shield
    "SSH":   "swsh1",
    "RCL":   "swsh2",
    "DAA":   "swsh3",
    "CPA":   "swsh35",
    "VIV":   "swsh4",
    "SHF":   "swsh45",
    "BST":   "swsh5",
    "CRE":   "swsh6",
    "EVS":   "swsh7",
    "CEL":   "swsh8",
    "FST":   "swsh9",
    "BRS":   "swsh10",
    "ASR":   "swsh11",
    "LOR":   "swsh12",
    "SIT":   "swsh13",
    "CRZ":   "swsh12pt5",
    "PR-SW": "swshp",
    # Scarlet & Violet
    "SV1":   "sv1",
    "SVI":   "sv1",
    "PAL":   "sv2",
    "OBF":   "sv3",
    "MEW":   "sv3pt5",
    "PAF":   "sv4pt5",
    "TEF":   "sv4",
    "TWM":   "sv6",
    "SFA":   "sv6pt5",
    "SCR":   "sv7",
    "SSP":   "sv8",
    "PRE":   "sv8pt5",
    "JTG":   "sv9",
    "PR-SV": "svp",
    "SVP":   "svp",
    # Custom / local sets (no pokemontcg.io equivalent — will gracefully fail)
    "ASC":   None,
    "POR":   None,
}


def get_tcgio_code(internal_code):
    """Return the pokemontcg.io set code for an internal code, or None if unmapped."""
    return SET_CODE_MAP.get(internal_code.upper())


class Command(BaseCommand):
    help = "Download hi-res card images from pokemontcg.io"

    def add_arguments(self, parser):
        parser.add_argument("--set",       dest="set_code")
        parser.add_argument("--force",     action="store_true")
        parser.add_argument("--dry-run",   action="store_true")
        parser.add_argument("--delay-min", type=float, default=DELAY_MIN)
        parser.add_argument("--delay-max", type=float, default=DELAY_MAX)

    def handle(self, *args, **options):
        set_filter = options["set_code"]
        force      = options["force"]
        dry_run    = options["dry_run"]
        dmin       = options["delay_min"]
        dmax       = options["delay_max"]

        base_dir = Path(settings.MEDIA_ROOT) / "card_images" / "originals"
        base_dir.mkdir(parents=True, exist_ok=True)

        progress = self._load_progress()

        qs = PokemonProduct.objects.select_related("card_set").values(
            "card_set__code", "card_number"
        ).distinct()
        if set_filter:
            qs = qs.filter(card_set__code=set_filter)

        work = {}
        for row in qs:
            sc, num = row["card_set__code"], row["card_number"]
            if sc and num:
                work[f"{sc}:{num}"] = (sc, num)

        total, done, skipped, failed, unmapped = len(work), 0, 0, [], []

        self.stdout.write(self.style.HTTP_INFO(
            f"\\n{\'[DRY RUN] \' if dry_run else \'\'}Queued {total} unique card images\\n"
        ))

        for i, (key, (sc, num)) in enumerate(work.items(), 1):
            # Check set mapping first
            tcgio_code = get_tcgio_code(sc)
            if tcgio_code is None:
                unmapped.append(f"{sc}/{num}")
                continue

            if key in progress.get("completed", set()) and not force:
                skipped += 1
                continue

            dest_dir  = base_dir / sc
            dest_file = dest_dir / f"{num}.png"

            if dest_file.exists() and not force:
                progress.setdefault("completed", set()).add(key)
                skipped += 1
                continue

            if dry_run:
                self.stdout.write(f"  [DRY] {sc}/{num}.png  (cdn: {tcgio_code}/{num})")
                done += 1
                continue

            url = self._get_image_url(tcgio_code, num)
            if not url:
                self.stdout.write(self.style.WARNING(f"  ✗ No image: {sc}/{num}  (tried: {tcgio_code}-{num})"))
                failed.append(key)
                time.sleep(random.uniform(dmin, dmax))
                continue

            if self._download(url, dest_dir, dest_file):
                done += 1
                progress.setdefault("completed", set()).add(key)
                self.stdout.write(f"  ✓ [{i}/{total}] {sc}/{num}.png")
            else:
                failed.append(key)
                self.stdout.write(self.style.WARNING(f"  ✗ [{i}/{total}] failed: {sc}/{num}"))

            if i % BURST_EVERY == 0:
                self.stdout.write(self.style.HTTP_INFO(
                    f"  ⏸  Burst pause {BURST_PAUSE}s after {BURST_EVERY} requests…"
                ))
                time.sleep(BURST_PAUSE)
            else:
                time.sleep(random.uniform(dmin, dmax))

            if i % 10 == 0:
                self._save_progress(progress)

        self._save_progress(progress)

        self.stdout.write("\\n" + "─" * 50)
        self.stdout.write(self.style.SUCCESS(f"  Downloaded : {done}"))
        self.stdout.write(self.style.HTTP_INFO(f"  Skipped    : {skipped}"))
        if unmapped:
            unique_unmapped = sorted(set(u.split("/")[0] for u in unmapped))
            self.stdout.write(self.style.WARNING(
                f"  Unmapped   : {len(unmapped)} cards across sets: {', '.join(unique_unmapped)}"
            ))
        if failed:
            self.stdout.write(self.style.ERROR(f"  Failed     : {len(failed)}"))
            for f in failed[:20]:
                self.stdout.write(f"    - {f}")
        self.stdout.write("─" * 50 + "\\n")

    def _get_image_url(self, tcgio_code, num):
        """Try CDN first (fast), fall back to REST API."""
        cdn = f"{IMAGES_CDN}/{tcgio_code}/{num}_hires.png"
        try:
            r = requests.head(cdn, headers=HEADERS, timeout=10)
            if r.status_code == 200:
                return cdn
        except requests.RequestException:
            pass
        # REST API fallback
        card_id = f"{tcgio_code}-{num}"
        try:
            r = requests.get(f"{POKEMONTCG_API}/{card_id}", headers=HEADERS, timeout=15)
            if r.status_code == 200:
                d = r.json().get("data", {})
                return d.get("images", {}).get("large") or d.get("images", {}).get("small")
        except requests.RequestException:
            pass
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
'''

with open(PATH, "w", encoding="utf-8") as fh:
    fh.write(CONTENT)

print(f"✓ Patched: {PATH}")
print()
print("Now stop the current download (Ctrl+C), then re-run:")
print("  python manage.py download_card_images")
print()
print("Already-downloaded images are safe — progress file will skip them.")
print()
print("Sets mapped to None (no pokemontcg.io equivalent, will be skipped):")
print("  ASC  — Ascended Heroes (your custom set)")
print("  POR  — Perfect Order (your custom set)")
