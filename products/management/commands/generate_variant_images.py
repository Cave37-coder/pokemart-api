"""
Management command: generate_variant_images
============================================
Generates watermarked variant images for true multi-variant cards only.
Organised by era folder, named with set+number+name+variant.

RULE: Only stamps cards where 2+ products share the same set+card_number.
Single-print cards (EX, Full Art, Secret Rare etc.) are skipped.

Folder: media/card_images/variants/{Era}/
File:   {SET}-{NUM}-{Name}-{VARIANT}.png

Examples:
    WotC/BS-004-Charizard-1st.png
    SV-Era/SV1-025-Pikachu-RH.png
    Custom/ASC-001-Ericas-Oddish-RH.png

Usage:
    python manage.py generate_variant_images
    python manage.py generate_variant_images --set SCR
    python manage.py generate_variant_images --force
    python manage.py generate_variant_images --opacity 0.45
    python manage.py generate_variant_images --test SCR 1
    python manage.py generate_variant_images --audit
"""

import os, io
from pathlib import Path
from collections import defaultdict
from django.core.management.base import BaseCommand
from django.conf import settings

try:
    from PIL import Image, ImageDraw, ImageFont, ImageChops
    PILLOW_OK = True
    PILLOW_VER = getattr(Image, "__version__", "unknown")
except ImportError:
    PILLOW_OK = False
    PILLOW_VER = "not installed"

NO_OVERLAY      = {"N"}
DEFAULT_OPACITY = 0.45

ART_TOP_RATIO    = 0.115
ART_BOTTOM_RATIO = 0.620
STORE_NAME       = "PokeBulk SA"
TEXT_COLOR       = (255, 255, 255)
FONT_SCALE       = 0.085
VARIANT_SCALE    = 0.062
LINE_GAP_RATIO   = 0.018

VARIANT_LABELS = {
    "H":      "Holofoil",
    "RH":     "Reverse Holo",
    "ERH":    "ETB Reverse Holo",
    "RH-PB":  "Poke Ball Holo",
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
    "SIR":    "Special Illus. Rare",
    "HR":     "Hyper Rare",
}


import re

# Era folder mapping — internal set code → era folder name
ERA_MAP = {
    # WotC
    "BS":    "WotC", "JU":  "WotC", "FO":  "WotC", "B2":  "WotC",
    "TR":    "WotC", "G1":  "WotC", "G2":  "WotC",
    "N1":    "WotC", "N2":  "WotC", "N3":  "WotC", "N4":  "WotC",
    "LC":    "WotC",
    # EX Era
    "RS":    "EX-Era", "SS":  "EX-Era", "DR":  "EX-Era", "MA":  "EX-Era",
    "HL":    "EX-Era", "RG":  "EX-Era", "TRR": "EX-Era", "DX":  "EX-Era",
    "EM":    "EX-Era", "UF":  "EX-Era", "DS":  "EX-Era", "LM":  "EX-Era",
    "HP":    "EX-Era", "CG":  "EX-Era", "DF":  "EX-Era", "PK":  "EX-Era",
    # DP Era
    "DP":    "DP-Era", "MT":  "DP-Era", "SW":  "DP-Era", "GE":  "DP-Era",
    "MD":    "DP-Era", "LA":  "DP-Era", "SF":  "DP-Era",
    "PL":    "DP-Era", "RR":  "DP-Era", "AR":  "DP-Era",
    "HS":    "DP-Era", "UL":  "DP-Era", "UD":  "DP-Era",
    "TM":    "DP-Era", "CL":  "DP-Era",
    # BW Era
    "BLW":   "BW-Era", "EPO": "BW-Era", "NVI": "BW-Era", "NXD": "BW-Era",
    "DEX":   "BW-Era", "DRX": "BW-Era", "DRV": "BW-Era", "BCR": "BW-Era",
    "PLS":   "BW-Era", "PLF": "BW-Era", "PLB": "BW-Era",
    "LTR":   "BW-Era", "DCR": "BW-Era",
    # XY Era
    "XY":    "XY-Era", "FLF": "XY-Era", "FFI": "XY-Era", "PHF": "XY-Era",
    "PRC":   "XY-Era", "ROS": "XY-Era", "AOR": "XY-Era", "BKT": "XY-Era",
    "BKP":   "XY-Era", "FCO": "XY-Era", "STS": "XY-Era", "EVO": "XY-Era",
    "GEN":   "XY-Era", "PR-XY": "XY-Era",
    # SM Era
    "SUM":   "SM-Era", "GRI": "SM-Era", "BUS": "SM-Era", "SLG": "SM-Era",
    "CIN":   "SM-Era", "UPR": "SM-Era", "FLI": "SM-Era", "CES": "SM-Era",
    "DRM":   "SM-Era", "LOT": "SM-Era", "TEU": "SM-Era", "DET": "SM-Era",
    "UNB":   "SM-Era", "UNM": "SM-Era", "HIF": "SM-Era", "CEC": "SM-Era",
    "PR-SM": "SM-Era",
    # SWSH Era
    "SSH":   "SWSH-Era", "RCL": "SWSH-Era", "DAA": "SWSH-Era", "CPA": "SWSH-Era",
    "VIV":   "SWSH-Era", "SHF": "SWSH-Era", "BST": "SWSH-Era", "CRE": "SWSH-Era",
    "EVS":   "SWSH-Era", "CEL": "SWSH-Era", "FST": "SWSH-Era", "BRS": "SWSH-Era",
    "ASR":   "SWSH-Era", "LOR": "SWSH-Era", "SIT": "SWSH-Era", "CRZ": "SWSH-Era",
    "PR-SW": "SWSH-Era",
    # SV Era
    "SV1":   "SV-Era", "SVI": "SV-Era", "PAL": "SV-Era", "OBF": "SV-Era",
    "MEW":   "SV-Era", "PAF": "SV-Era", "TEF": "SV-Era", "TWM": "SV-Era",
    "SFA":   "SV-Era", "SCR": "SV-Era", "SSP": "SV-Era", "PRE": "SV-Era",
    "JTG":   "SV-Era", "PR-SV": "SV-Era", "SVP": "SV-Era",
    # Custom
    "ASC":   "Custom",
    "POR":   "Custom",
}

# pokemontcg.io CDN code mapping
SET_CODE_MAP = {
    "BS":"base1","JU":"base2","FO":"base3","B2":"base4","TR":"base5",
    "G1":"gym1","G2":"gym2","N1":"neo1","N2":"neo2","N3":"neo3","N4":"neo4",
    "LC":"lc","EX":"expedition","AQ":"aquapolis","SK":"skyridge",
    "RS":"ex1","SS":"ex2","DR":"ex3","MA":"ex4","HL":"ex5","RG":"ex6",
    "TRR":"ex7","DX":"ex8","EM":"ex9","UF":"ex10","DS":"ex11","LM":"ex12",
    "HP":"ex13","CG":"ex14","DF":"ex15","PK":"ex16",
    "DP":"dp1","MT":"dp2","SW":"dp3","GE":"dp4","MD":"dp5","LA":"dp6","SF":"dp7",
    "PL":"pl1","RR":"pl2","SV":"pl3","AR":"pl4",
    "HS":"hgss1","UL":"hgss2","UD":"hgss3","TM":"hgss4","CL":"col1",
    "BLW":"bw1","EPO":"bw2","NVI":"bw3","NXD":"bw4","DEX":"bw5","DRX":"bw6",
    "DRV":"dv1","BCR":"bw7","PLS":"bw8","PLF":"bw9","PLB":"bw10",
    "LTR":"bw11","DCR":"dc1",
    "XY":"xy1","FLF":"xy2","FFI":"xy3","PHF":"xy4","PRC":"xy5","ROS":"xy6",
    "AOR":"xy7","BKT":"xy8","BKP":"xy9","FCO":"xy10","STS":"xy11","EVO":"xy12",
    "GEN":"g1","PR-XY":"xyp",
    "SUM":"sm1","GRI":"sm2","BUS":"sm3","SLG":"sm35","CIN":"sm4","UPR":"sm5",
    "FLI":"sm6","CES":"sm7","DRM":"sm75","LOT":"sm8","TEU":"sm9","DET":"det1",
    "UNB":"sm10","UNM":"sm11","HIF":"sm115","CEC":"sm12","PR-SM":"smp",
    "SSH":"swsh1","RCL":"swsh2","DAA":"swsh3","CPA":"swsh35","VIV":"swsh4",
    "SHF":"swsh45","BST":"swsh5","CRE":"swsh6","EVS":"swsh7","CEL":"swsh8",
    "FST":"swsh9","BRS":"swsh10","ASR":"swsh11","LOR":"swsh12","SIT":"swsh13",
    "CRZ":"swsh12pt5","PR-SW":"swshp",
    "SV1":"sv1","SVI":"sv1","PAL":"sv2","OBF":"sv3","MEW":"sv3pt5","PAF":"sv4pt5",
    "TEF":"sv4","TWM":"sv6","SFA":"sv6pt5","SCR":"sv7","SSP":"sv8","PRE":"sv8pt5",
    "JTG":"sv9","PR-SV":"svp","SVP":"svp",
    "ASC":None,"POR":None,
}


def get_era(set_code):
    return ERA_MAP.get(set_code.upper(), "Other")


def get_tcgio_code(set_code):
    return SET_CODE_MAP.get(set_code.upper())


def make_filename(set_code, card_number, card_name, variant=None):
    """
    Build descriptive filename.
    e.g. ASC-001-Ericas-Oddish.png  or  ASC-001-Ericas-Oddish-RH.png
    """
    try:
        padded = str(int(card_number)).zfill(3)
    except (ValueError, TypeError):
        padded = str(card_number)  # TG01, GG01 etc — keep as-is

    # Sanitise name: strip apostrophes/special chars, spaces → hyphens
    safe_name = re.sub(r"[^\w\s-]", "", card_name or "Unknown")
    safe_name = re.sub(r"\s+", "-", safe_name.strip())
    safe_name = re.sub(r"-+", "-", safe_name).strip("-")

    if variant:
        safe_v = variant.replace("/", "-").replace("\\", "-")
        return f"{set_code}-{padded}-{safe_name}-{safe_v}.png"
    return f"{set_code}-{padded}-{safe_name}.png"


def build_variant_map(set_filter=None):
    from products.models import PokemonProduct
    qs = PokemonProduct.objects.select_related("card_set").values(
        "card_set__code", "card_number", "variant_override", "name"
    )
    if set_filter:
        qs = qs.filter(card_set__code=set_filter)
    variant_map = defaultdict(list)
    name_map    = {}
    for row in qs:
        sc  = row["card_set__code"]
        num = row["card_number"]
        var = row["variant_override"] or ""
        nm  = row["name"] or "Unknown"
        if sc and num:
            variant_map[(sc, num)].append(var)
            if (sc, num) not in name_map:
                name_map[(sc, num)] = nm
    return variant_map, name_map


class Command(BaseCommand):
    help = "Generate watermarked variant images (multi-variant cards only)"

    def add_arguments(self, parser):
        parser.add_argument("--set",     dest="set_code")
        parser.add_argument("--force",   action="store_true")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--opacity", type=float, default=DEFAULT_OPACITY)
        parser.add_argument("--test",    nargs=2, metavar=("SET", "NUM"))
        parser.add_argument("--audit",   action="store_true")

    def handle(self, *args, **options):
        if not PILLOW_OK:
            self.stderr.write(self.style.ERROR(
                "Pillow not installed. Run:\n"
                "  pip install --upgrade Pillow --break-system-packages"
            ))
            return

        self.stdout.write(f"Pillow {PILLOW_VER}")

        set_filter = options["set_code"]
        force      = options["force"]
        dry_run    = options["dry_run"]
        opacity    = max(0.05, min(0.80, options["opacity"]))
        test_args  = options.get("test")
        audit      = options.get("audit")

        orig_base    = Path(settings.MEDIA_ROOT) / "card_images" / "originals"
        variant_base = Path(settings.MEDIA_ROOT) / "card_images" / "variants"
        variant_base.mkdir(parents=True, exist_ok=True)

        variant_map, name_map = build_variant_map(set_filter)
        multi_keys = {k for k, v in variant_map.items() if len(v) >= 2}

        # ── Test mode ────────────────────────────────────────────────────────
        if test_args:
            sc, num = test_args
            name     = name_map.get((sc, num), "Unknown")
            era      = get_era(sc)
            orig     = orig_base / era / make_filename(sc, num, name)
            if not orig.exists():
                self.stderr.write(self.style.ERROR(f"Original not found: {orig}"))
                self.stderr.write("Has download_card_images been run yet?")
                return
            out_dir  = variant_base / era
            out_file = out_dir / make_filename(sc, num, name, "TEST-RH")
            self.stdout.write(f"Stamping: {orig}  (opacity={opacity})")
            try:
                self._stamp(orig, out_dir, out_file, "RH", opacity)
                self.stdout.write(self.style.SUCCESS(f"Saved: {out_file}"))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Failed: {e}"))
                import traceback; traceback.print_exc()
            return

        # ── Audit mode ───────────────────────────────────────────────────────
        if audit:
            self.stdout.write(self.style.HTTP_INFO(
                f"\n{len(multi_keys)} cards qualify for watermarking:\n"
            ))
            for (sc, num) in sorted(multi_keys):
                name     = name_map.get((sc, num), "?")
                era      = get_era(sc)
                variants = sorted(variant_map[(sc, num)])
                self.stdout.write(
                    f"  [{era}] {make_filename(sc, num, name)}  "
                    f"→  {', '.join(variants)}"
                )
            single_non_n = {
                k for k, v in variant_map.items()
                if len(v) == 1 and v[0] not in ("N", "")
            }
            self.stdout.write(self.style.WARNING(
                f"\n{len(single_non_n)} unique prints correctly skipped:"
            ))
            for (sc, num) in sorted(single_non_n)[:20]:
                self.stdout.write(
                    f"  {make_filename(sc, num, name_map.get((sc,num),'?'))}  "
                    f"[{variant_map[(sc,num)][0]}]"
                )
            if len(single_non_n) > 20:
                self.stdout.write(f"  ... +{len(single_non_n)-20} more")
            return

        # ── Batch mode ───────────────────────────────────────────────────────
        from products.models import PokemonProduct
        qs = PokemonProduct.objects.select_related("card_set").all()
        if set_filter:
            qs = qs.filter(card_set__code=set_filter)
        qs = qs.exclude(variant_override__in=["N", "", None])

        done, skipped, skipped_unique, missing = 0, 0, 0, []

        self.stdout.write(self.style.HTTP_INFO(
            f"\n{'[DRY RUN] ' if dry_run else ''}opacity={opacity}\n"
        ))

        for product in qs:
            sc      = product.card_set.code if product.card_set else None
            num     = product.card_number
            variant = product.variant_override
            name    = product.name or "Unknown"

            if not sc or not num or not variant:
                continue

            if (sc, num) not in multi_keys:
                skipped_unique += 1
                continue

            era      = get_era(sc)
            orig     = orig_base / era / make_filename(sc, num, name)
            if not orig.exists():
                missing.append(f"{era}/{make_filename(sc, num, name)}")
                continue

            out_dir  = variant_base / era
            out_file = out_dir / make_filename(sc, num, name, variant)

            if out_file.exists() and not force:
                skipped += 1
                continue

            if dry_run:
                self.stdout.write(
                    f"  [DRY] {era}/{make_filename(sc, num, name, variant)}"
                )
                done += 1
                continue

            try:
                self._stamp(orig, out_dir, out_file, variant, opacity)
                done += 1
                self.stdout.write(f"  ✓ {era}/{make_filename(sc, num, name, variant)}")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  ✗ {sc}/{num}: {e}"))

        self.stdout.write("\n" + "─" * 50)
        self.stdout.write(self.style.SUCCESS(f"  Generated        : {done}"))
        self.stdout.write(self.style.HTTP_INFO(f"  Already exists   : {skipped}"))
        self.stdout.write(self.style.HTTP_INFO(
            f"  Unique prints skipped : {skipped_unique}"
        ))
        if missing:
            um = sorted(set(missing))
            self.stdout.write(self.style.WARNING(f"  No original : {len(um)}"))
            for m in um[:15]:
                self.stdout.write(f"    - {m}")
        self.stdout.write("─" * 50 + "\n")

    def _stamp(self, orig_file, out_dir, out_file, variant, opacity):
        out_dir.mkdir(parents=True, exist_ok=True)
        raw = orig_file.read_bytes()
        img = Image.open(io.BytesIO(raw))
        if img.mode == "P":
            img = img.convert("RGBA")
        elif img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
        img = img.convert("RGBA")
        w, h = img.size

        art_top    = int(h * ART_TOP_RATIO)
        art_bottom = int(h * ART_BOTTOM_RATIO)
        art_mid_y  = art_top + (art_bottom - art_top) // 2

        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw    = ImageDraw.Draw(overlay)

        fs_s = max(18, int(w * FONT_SCALE))
        fs_v = max(14, int(w * VARIANT_SCALE))
        gap  = int(h * LINE_GAP_RATIO)

        sf = self._font(fs_s)
        vf = self._font(fs_v)

        sl = STORE_NAME
        vl = VARIANT_LABELS.get(variant, variant)

        sb = draw.textbbox((0,0), sl, font=sf)
        vb = draw.textbbox((0,0), vl, font=vf)
        sw, sh = sb[2]-sb[0], sb[3]-sb[1]
        vw, vh = vb[2]-vb[0], vb[3]-vb[1]

        bt = art_mid_y - (sh + gap + vh) // 2
        sx = (w-sw)//2;  sy = bt
        vx = (w-vw)//2;  vy = bt + sh + gap

        alpha     = int(255 * opacity)
        box_alpha = int(255 * opacity * 0.45)
        px, py    = 20, 14

        draw.rounded_rectangle(
            [max(8,min(sx,vx)-px), max(art_top+4, sy-py),
             min(w-8,max(sx+sw,vx+vw)+px), min(art_bottom-4, vy+vh+py)],
            radius=10, fill=(0,0,0,box_alpha)
        )
        sa = int(alpha*0.55)
        draw.text((sx+2,sy+2), sl, font=sf, fill=(0,0,0,sa))
        draw.text((vx+2,vy+2), vl, font=vf, fill=(0,0,0,sa))
        draw.text((sx,sy), sl, font=sf, fill=(*TEXT_COLOR,alpha))
        draw.text((vx,vy), vl, font=vf, fill=(*TEXT_COLOR,int(alpha*0.88)))

        mask = Image.new("L", (w,h), 0)
        mask.paste(255, (0, art_top, w, art_bottom))
        r,g,b,a = overlay.split()
        a = ImageChops.multiply(a, mask)
        overlay = Image.merge("RGBA", (r,g,b,a))

        Image.alpha_composite(img, overlay).convert("RGB").save(
            str(out_file), format="PNG", optimize=True
        )

    def _font(self, size):
        for p in ["C:/Windows/Fonts/arialbd.ttf","C:/Windows/Fonts/calibrib.ttf",
                  "C:/Windows/Fonts/verdanab.ttf","C:/Windows/Fonts/arial.ttf",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]:
            if os.path.exists(p):
                try:
                    return ImageFont.truetype(p, size)
                except Exception:
                    continue
        return ImageFont.load_default()
