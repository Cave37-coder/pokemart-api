"""
Run this script from your project root to install both management commands.

    cd C:\\Users\\texca\\pokemart-api
    python write_image_commands.py
"""

import os

BASE = os.path.join("products", "management", "commands")
os.makedirs(BASE, exist_ok=True)

# Ensure __init__ files exist
for d in [
    os.path.join("products", "management"),
    BASE,
]:
    init = os.path.join(d, "__init__.py")
    if not os.path.exists(init):
        open(init, "w").close()

# ── Command 1: download_card_images ─────────────────────────────────────────
CMD1 = '''"""
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

DELAY_MIN  = 1.2
DELAY_MAX  = 2.8
BURST_PAUSE = 8.0
BURST_EVERY = 25

HEADERS = {"User-Agent": "PokeBulkSA/1.0 (pokebulksa.co.za; card image archiver)"}
if hasattr(settings, "POKEMONTCG_API_KEY") and settings.POKEMONTCG_API_KEY:
    HEADERS["X-Api-Key"] = settings.POKEMONTCG_API_KEY


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

        total, done, skipped, failed = len(work), 0, 0, []
        self.stdout.write(self.style.HTTP_INFO(
            f"\\n{\'[DRY RUN] \' if dry_run else \'\'}Queued {total} unique card images\\n"
        ))

        for i, (key, (sc, num)) in enumerate(work.items(), 1):
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
                self.stdout.write(f"  [DRY] {sc}/{num}.png")
                done += 1
                continue

            url = self._get_image_url(sc, num)
            if not url:
                self.stdout.write(self.style.WARNING(f"  ✗ No image: {sc}/{num}"))
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
                self.stdout.write(self.style.HTTP_INFO(f"  ⏸  Burst pause {BURST_PAUSE}s…"))
                time.sleep(BURST_PAUSE)
            else:
                time.sleep(random.uniform(dmin, dmax))

            if i % 10 == 0:
                self._save_progress(progress)

        self._save_progress(progress)
        self.stdout.write("\\n" + "─" * 50)
        self.stdout.write(self.style.SUCCESS(f"  Downloaded : {done}"))
        self.stdout.write(self.style.HTTP_INFO(f"  Skipped    : {skipped}"))
        if failed:
            self.stdout.write(self.style.ERROR(f"  Failed     : {len(failed)}"))
            for f in failed[:20]:
                self.stdout.write(f"    - {f}")
        self.stdout.write("─" * 50 + "\\n")

    def _get_image_url(self, sc, num):
        sc_lower = sc.lower()
        cdn = f"{IMAGES_CDN}/{sc_lower}/{num}_hires.png"
        try:
            r = requests.head(cdn, headers=HEADERS, timeout=10)
            if r.status_code == 200:
                return cdn
        except requests.RequestException:
            pass
        try:
            r = requests.get(f"{POKEMONTCG_API}/{sc_lower}-{num}", headers=HEADERS, timeout=15)
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

# ── Command 2: generate_variant_images ───────────────────────────────────────
CMD2 = '''"""
Management command: generate_variant_images
============================================
Reads clean originals from media/card_images/originals/
and generates a watermarked copy for every non-Normal PokemonProduct.
Watermark is confined strictly to the art-box zone of the card.

Usage:
    python manage.py generate_variant_images
    python manage.py generate_variant_images --set sv3pt5
    python manage.py generate_variant_images --force
    python manage.py generate_variant_images --opacity 0.18

Output:
    media/card_images/variants/{set_code}/{card_number}_{variant}.png

Requires:
    pip install Pillow --break-system-packages
"""

import os
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings

try:
    from PIL import Image, ImageDraw, ImageFont, ImageChops
    PILLOW_OK = True
except ImportError:
    PILLOW_OK = False

NO_OVERLAY = {"N", "DR"}

ART_TOP_RATIO    = 0.115
ART_BOTTOM_RATIO = 0.620

STORE_NAME     = "PokéBulk SA"
TEXT_COLOR     = (255, 255, 255)
FONT_SCALE     = 0.055
VARIANT_SCALE  = 0.040
LINE_GAP_RATIO = 0.015

VARIANT_LABELS = {
    "H":      "Holofoil",
    "RH":     "Reverse Holo",
    "ERH":    "ETB Reverse Holo",
    "RH-PB":  "Poké Ball Holo",
    "RH-MB":  "Master Ball Holo",
    "BRH-FB": "Fast Ball Holo",
    "BRH-LB": "Luxury Ball Holo",
    "BRH-QB": "Quick Ball Holo",
    "BRH-DB": "Dusk Ball Holo",
    "BRH-R":  "Rocket Ball Holo",
    "AS":     "Ace Spec",
    "MH":     "Mirror Holo",
    "1st":    "1st Edition",
    "IR":     "Illustration Rare",
    "SIR":    "Special Illustration Rare",
    "HR":     "Hyper Rare",
}


class Command(BaseCommand):
    help = "Generate watermarked variant images from clean card originals"

    def add_arguments(self, parser):
        parser.add_argument("--set",     dest="set_code")
        parser.add_argument("--force",   action="store_true")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--opacity", type=float, default=0.17)

    def handle(self, *args, **options):
        if not PILLOW_OK:
            self.stderr.write(self.style.ERROR(
                "Pillow not installed. Run:\\n  pip install Pillow --break-system-packages"
            ))
            return

        from products.models import PokemonProduct

        set_filter = options["set_code"]
        force      = options["force"]
        dry_run    = options["dry_run"]
        opacity    = max(0.05, min(0.40, options["opacity"]))

        orig_base    = Path(settings.MEDIA_ROOT) / "card_images" / "originals"
        variant_base = Path(settings.MEDIA_ROOT) / "card_images" / "variants"
        variant_base.mkdir(parents=True, exist_ok=True)

        qs = PokemonProduct.objects.select_related("card_set").all()
        if set_filter:
            qs = qs.filter(card_set__code=set_filter)
        qs = qs.exclude(variant_override__in=list(NO_OVERLAY) + ["", None])

        total, done, skipped, missing = qs.count(), 0, 0, []
        self.stdout.write(self.style.HTTP_INFO(
            f"\\n{\'[DRY RUN] \' if dry_run else \'\'}Processing {total} variant products (opacity={opacity})\\n"
        ))

        for product in qs:
            sc      = product.card_set.code if product.card_set else None
            num     = product.card_number
            variant = product.variant_override

            if not sc or not num or not variant:
                continue

            orig = orig_base / sc / f"{num}.png"
            if not orig.exists():
                missing.append(f"{sc}/{num}")
                continue

            safe_v   = variant.replace("/", "-").replace("\\\\", "-")
            out_dir  = variant_base / sc
            out_file = out_dir / f"{num}_{safe_v}.png"

            if out_file.exists() and not force:
                skipped += 1
                continue

            if dry_run:
                self.stdout.write(
                    f"  [DRY] {sc}/{num}_{safe_v}.png  [{VARIANT_LABELS.get(variant, variant)}]"
                )
                done += 1
                continue

            try:
                self._stamp(orig, out_dir, out_file, variant, opacity)
                done += 1
                self.stdout.write(f"  ✓ {sc}/{num}_{safe_v}.png")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  ✗ {sc}/{num}: {e}"))

        self.stdout.write("\\n" + "─" * 50)
        self.stdout.write(self.style.SUCCESS(f"  Generated : {done}"))
        self.stdout.write(self.style.HTTP_INFO(f"  Skipped   : {skipped}"))
        if missing:
            um = sorted(set(missing))
            self.stdout.write(self.style.WARNING(f"  No orig   : {len(um)} (run download_card_images first)"))
            for m in um[:15]:
                self.stdout.write(f"    - {m}")
            if len(um) > 15:
                self.stdout.write(f"    … +{len(um)-15} more")
        self.stdout.write("─" * 50 + "\\n")

    def _stamp(self, orig_file, out_dir, out_file, variant, opacity):
        out_dir.mkdir(parents=True, exist_ok=True)

        img = Image.open(orig_file).convert("RGBA")
        w, h = img.size

        art_top    = int(h * ART_TOP_RATIO)
        art_bottom = int(h * ART_BOTTOM_RATIO)
        art_h      = art_bottom - art_top
        art_mid_y  = art_top + art_h // 2

        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw    = ImageDraw.Draw(overlay)

        fs_store   = max(12, int(w * FONT_SCALE))
        fs_variant = max(10, int(w * VARIANT_SCALE))
        gap        = int(h * LINE_GAP_RATIO)

        sfont = self._font(fs_store)
        vfont = self._font(fs_variant)

        slabel = STORE_NAME
        vlabel = VARIANT_LABELS.get(variant, variant)

        sb = draw.textbbox((0, 0), slabel, font=sfont)
        vb = draw.textbbox((0, 0), vlabel, font=vfont)
        sw, sh = sb[2]-sb[0], sb[3]-sb[1]
        vw, vh = vb[2]-vb[0], vb[3]-vb[1]

        block_top = art_mid_y - (sh + gap + vh) // 2

        sx = (w - sw) // 2
        vx = (w - vw) // 2
        sy = block_top
        vy = block_top + sh + gap

        alpha     = int(255 * opacity)
        box_alpha = int(alpha * 0.35)
        pad       = 12

        draw.rounded_rectangle(
            [max(8, min(sx,vx)-pad), max(art_top+4, sy-pad),
             min(w-8, max(sx+sw,vx+vw)+pad), min(art_bottom-4, vy+vh+pad)],
            radius=6, fill=(0, 0, 0, box_alpha)
        )
        draw.text((sx, sy), slabel, font=sfont, fill=(*TEXT_COLOR, alpha))
        draw.text((vx, vy), vlabel, font=vfont, fill=(*TEXT_COLOR, int(alpha*0.80)))

        # Clip overlay to art zone rows only
        mask = Image.new("L", (w, h), 0)
        mask.paste(255, (0, art_top, w, art_bottom))

        r, g, b, a = overlay.split()
        a = ImageChops.multiply(a, mask)
        overlay = Image.merge("RGBA", (r, g, b, a))

        result = Image.alpha_composite(img, overlay)
        result.convert("RGB").save(out_file, "PNG", optimize=True)

    def _font(self, size):
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/arial.ttf",
        ]
        for p in candidates:
            if os.path.exists(p):
                try:
                    return ImageFont.truetype(p, size)
                except Exception:
                    continue
        return ImageFont.load_default()
'''

# Write files
files = {
    os.path.join(BASE, "download_card_images.py"): CMD1,
    os.path.join(BASE, "generate_variant_images.py"): CMD2,
}

for path, content in files.items():
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    print(f"✓ Written: {path}")

print("\n✅ Both management commands installed.")
print("\nNext steps:")
print("  1.  pip install Pillow --break-system-packages")
print("  2.  python manage.py download_card_images")
print("  3.  python manage.py generate_variant_images")
print("\nOptional flags:")
print("  --set sv3pt5      → one set only")
print("  --force           → re-download / re-generate existing")
print("  --dry-run         → preview without writing")
print("  --opacity 0.20    → adjust watermark darkness (generate only)")
print("  --delay-min 2.0   → slower if getting rate-limited (download only)")
