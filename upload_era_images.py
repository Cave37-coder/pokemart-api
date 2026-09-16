# upload_era_images.py
# Uploads ERA-level logos + symbols from Michael's local "ERA" folder to R2,
# then updates Railway DB with the CDN URLs.
#
# Why this exists (2026-09-16): the live Era.logo_url values for most eras
# turned out to be Bulbapedia WIKI PAGE links (e.g. ".../wiki/Base_Set_(TCG)
# #/media/File:Pok%C3%A9mon_TCG_logo_old.png"), not direct image files --
# that's a page URL, not image bytes, so every era card on /checklists fell
# back to its coloured text pill (the onError handler in EraHome silently
# swallows the broken <img>, see page.tsx eraBadge()). Re-hosting those via
# the admin's "Upload logo(s) to R2" action (products/admin.py) would have
# just saved the wiki page's HTML as if it were image bytes -- same
# underlying bug. This script sidesteps all of that by uploading straight
# from real local image files instead of re-fetching a pasted URL.
#
# Also adds Era.symbol_url (new field, migration 0035) -- a smaller per-era
# icon, parallel to CardSet.symbol_url, for the compact era-selection cards
# on /checklists (Michael, 2026-09-16: "the era symbols... so we can add
# them to the page for era selection").
#
# The Era table has legacy DUPLICATE rows per era (multiple `code`s sharing
# the same conceptual era, inconsistent " Era" suffix -- see
# checklistShared.ts's normalizeEraName() on the frontend, which exists
# specifically to paper over this). Keying this script off the era's NAME
# (normalized the exact same way) and writing every matching row, rather
# than one hand-picked code, means the frontend's name-lookup finds a good
# URL no matter which duplicate row it happens to land on first.
#
# Run from: pokemart-api folder, on Michael's machine (needs DB access)
# Command:  python upload_era_images.py

import os, re, sys, boto3
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
ERA_DIR   = Path("D:/D Downs/Card Pics/Set Symbols/ERA")
R2_BUCKET = "pokebulkcards"
R2_CDN    = "https://images.pokebulk.co.za"

# ── Mapping: canonical era label (matched by normalized NAME, so it applies
# to every duplicate Era row for that era) → (logo_filename, symbol_filename)
# logo   = wide wordmark banner (era card's "big" slot)
# symbol = small icon (what actually shows on the compact era-selection
#          card today -- see eraBadge() preferring symbol_url)
# Set either to None if this era doesn't have that asset in the folder yet.
ERA_MAP = {
    "WotC Base":        ("Base Set logo.png",      "original_series.png"),
    "WotC Neo":         (None,                      "neo_series.png"),
    "WotC Legendary":   ("Legendary Logo.png",      "legendary_collection.png"),
    # "WotC Other" covers the e-Card era sets (Expedition/Aquapolis/Skyridge)
    # in this catalog's bucketing -- ecard_series.png is the closest match
    # in the folder. No dedicated wordmark logo file found for this bucket.
    "WotC Other":       (None,                      "ecard_series.png"),
    "EX Era":           ("Ruby & Sapphire logo.png", "ex_series.png"),
    "Diamond & Pearl":  (None,                      "diamond_pearl_series.png"),
    "HG&SS":            (None,                      "heartgold_soulsilver_series.png"),
    "Black & White":    ("B&W Logo.png",            "black_white_series.png"),
    "XY Era":           ("XY Logo.png",             "xy_series.png"),
    "Sun & Moon":       ("S&M logo.png",             "sun_moon_series.png"),
    "Sword & Shield":   ("SWSH logo.png",            "sword_shield_series.png"),
    "Scarlet & Violet": ("S&V logo.png",             "scarlet_violet_series.png"),
    "Mega Evolution":   (None,                      "mega_evolution_series.png"),
    # Special Sets aren't wired up to a specific era's logo/symbol on the
    # frontend today (the home screen's "Special Sets" tile always shows
    # the plain text pill, see EraHome in checklists/page.tsx) -- included
    # here anyway so the DB has correct data ready for whenever that tile
    # gets its own image treatment.
    "Special - Prize Pack": ("Prize Pack logo.png", None),
}

# Same normalization the frontend's checklistShared.ts::normalizeEraName()
# uses -- trim, lowercase, drop a trailing " era", collapse whitespace.
def normalize_era_name(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"\s+era$", "", s)
    s = re.sub(r"\s+", " ", s)
    return s


def get_r2_client():
    from botocore.config import Config
    return boto3.client(
        "s3",
        endpoint_url="https://229506129ad4206787dd4d3227608e17.r2.cloudflarestorage.com",
        aws_access_key_id="fdff88cee69c515cf67d4ae275d1bc72",
        aws_secret_access_key="e7122d20bd2ad8121756a86f4165af40be5fd3efe40fbdca5f5ca922bb1ace8f",
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def find_file(filename):
    """Search for filename in the ERA folder and its subdirectories."""
    if not filename:
        return None
    p = ERA_DIR / filename
    if p.exists():
        return p
    for f in ERA_DIR.rglob(filename):
        return f
    return None


def content_type_for(path: Path) -> str:
    return "image/png" if path.suffix.lower() == ".png" else "image/jpeg"


def upload_file(s3, local_path: Path, r2_key: str) -> str:
    with open(str(local_path), "rb") as f:
        data = f.read()
    s3.put_object(Bucket=R2_BUCKET, Key=r2_key, Body=data, ContentType=content_type_for(local_path))
    return f"{R2_CDN}/{r2_key}"


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    sys.path.insert(0, str(Path(__file__).parent))
    import django
    django.setup()
    from products.models import Era

    s3 = get_r2_client()
    eras = list(Era.objects.all())
    by_norm_name = {}
    for e in eras:
        by_norm_name.setdefault(normalize_era_name(e.name), []).append(e)

    updated_rows = 0
    missing_file = []
    unmatched_labels = []

    for label, (logo_fn, symbol_fn) in ERA_MAP.items():
        rows = by_norm_name.get(normalize_era_name(label), [])
        if not rows:
            unmatched_labels.append(label)
            continue

        logo_url = None
        if logo_fn:
            local = find_file(logo_fn)
            if local:
                logo_url = upload_file(s3, local, f"eras/logos/{normalize_era_name(label).replace(' ', '_')}_logo{local.suffix.lower()}")
                print(f"  \u2713 {label} logo \u2192 {logo_url}")
            else:
                missing_file.append(f"{label} logo: {logo_fn}")
                print(f"  \u2717 {label} logo file not found: {logo_fn}")

        symbol_url = None
        if symbol_fn:
            local = find_file(symbol_fn)
            if local:
                symbol_url = upload_file(s3, local, f"eras/symbols/{normalize_era_name(label).replace(' ', '_')}_symbol{local.suffix.lower()}")
                print(f"  \u2713 {label} symbol \u2192 {symbol_url}")
            else:
                missing_file.append(f"{label} symbol: {symbol_fn}")
                print(f"  \u2717 {label} symbol file not found: {symbol_fn}")

        if not logo_url and not symbol_url:
            continue

        # Apply to EVERY duplicate row sharing this era's normalized name --
        # see the module docstring for why one hand-picked code isn't enough.
        for era in rows:
            fields = []
            if logo_url:
                era.logo_url = logo_url
                fields.append("logo_url")
            if symbol_url:
                era.symbol_url = symbol_url
                fields.append("symbol_url")
            era.save(update_fields=fields)
            updated_rows += 1
            print(f"    saved on Era(code={era.code!r}, name={era.name!r})")

    print(f"\nDone \u2014 {updated_rows} Era row(s) updated across {len(ERA_MAP)} era labels.")
    if unmatched_labels:
        print(f"\nLabels in ERA_MAP with no matching DB row ({len(unmatched_labels)}):")
        for m in unmatched_labels:
            print(f"  {m}")
    if missing_file:
        print(f"\nMissing local files ({len(missing_file)}):")
        for m in missing_file:
            print(f"  {m}")


if __name__ == "__main__":
    main()
