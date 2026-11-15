# upload_era_images.py
# Uploads ONE image per era from Michael's local "ERA" folder to R2, then
# points BOTH Era.logo_url and Era.symbol_url at it in the Railway DB.
#
# Why this exists (2026-09-16): the live Era.logo_url values for most eras
# turned out to be Bulbapedia WIKI PAGE links (e.g. ".../wiki/Base_Set_(TCG)
# #/media/File:Pok%C3%A9mon_TCG_logo_old.png"), not direct image files --
# that's a page URL, not image bytes, so every era card on /checklists fell
# back to its coloured text pill (the onError handler in EraHome silently
# swallows the broken <img>, see page.tsx eraBadge()). This script sidesteps
# that by uploading straight from real local image files instead of
# re-fetching a pasted URL.
#
# 2026-09-16, round 5 -- COLLAPSED to one image per era. Rounds 3-4 treated
# logo_url (era-detail-page banner) and symbol_url (compact home-screen
# card icon) as two potentially-different assets. In reality Michael only
# ever has ONE image per era -- confirmed by listing the ERA folder and
# finding every "... Symbol.png" file is byte-identical to an older
# "... Era.png" file of the exact same size, just renamed. There never was
# a second, different asset.
#
# Round 4's "clean fix" (clear whichever field ERA_MAP didn't supply a file
# for) was therefore wrong: for the 9 eras that only had a "symbol" file
# listed, it wiped their logo_url to '' -- which blanked the banner at the
# top of those eras' detail pages ([era]/page.tsx reads ONLY logo_url for
# that header), even though the same image Michael wanted was sitting
# right there as the symbol. That's the "where are the images we agreed on"
# regression.
#
# The actual fix: ERA_MAP is now `label -> single filename` (or None for an
# era with no image yet). Each file is uploaded ONCE and the resulting CDN
# url is written to BOTH logo_url and symbol_url -- so the one clean image
# Michael sent shows up everywhere an era's picture is used, home screen
# card and detail-page banner alike. Re-running is idempotent (same file ->
# same R2 key -> same url, no-op save) and self-cleaning (an era mapped to
# None here has both fields explicitly cleared, so a removed/retired image
# can't linger as a stale value the way Mega Evolution's did).
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
# to every duplicate Era row for that era) → single image filename, or None
# if this era doesn't have an image in the folder yet (both logo_url and
# symbol_url get explicitly cleared in that case, never left stale).
ERA_MAP = {
    "WotC Base":        "Wizards of the Coast Logo.jpg",
    "WotC Neo":         "Neo Symbol.png",
    "WotC Legendary":   "Legendary Collection Symbol.png",
    # "WotC Other" covers the e-Card era sets (Expedition/Aquapolis/Skyridge)
    # in this catalog's bucketing.
    "WotC Other":       "E-Card Symbol.png",
    "EX Era":           "EX Symbol.png",
    "Diamond & Pearl":  "Diamond and Pearl Symbol.png",
    "HG&SS":            "HeartGold SoulSilver Symbol.png",
    "Black & White":    "Black and White Symbol.png",
    "XY Era":           "XY Symbol.png",
    "Sun & Moon":       "Sun and Moon Symbol.png",
    "Sword & Shield":   "Sword and Shield Symbol.png",
    "Scarlet & Violet": "Scarlet and Violet Logo.png",
    "Mega Evolution":   "Mega Evolution Logo.png",
    # Special Sets aren't wired up to a specific era's image on the frontend
    # today (the home screen's "Special Sets" tile always shows the plain
    # text pill, see EraHome in checklists/page.tsx) -- no image for it yet.
    "Special - Prize Pack": None,
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

    for label, filename in ERA_MAP.items():
        rows = by_norm_name.get(normalize_era_name(label), [])
        if not rows:
            unmatched_labels.append(label)
            continue

        # url ends up one of:
        #   - a freshly uploaded CDN url (file specified and found)
        #   - '' (ERA_MAP has None for this era -> CLEAR any stale value on both fields)
        #   - None (file specified but not found this run -> leave both fields untouched)
        url = '' if filename is None else None
        if filename:
            local = find_file(filename)
            if local:
                slug = normalize_era_name(label).replace(' ', '_')
                url = upload_file(s3, local, f"eras/logos/{slug}_logo{local.suffix.lower()}")
                print(f"  \u2713 {label} \u2192 {url}")
            else:
                missing_file.append(f"{label}: {filename}")
                print(f"  \u2717 {label} file not found: {filename} (leaving existing values untouched)")

        # Apply to EVERY duplicate row sharing this era's normalized name --
        # see the module docstring for why one hand-picked code isn't enough.
        # Both fields point at the SAME url -- there's only one image per
        # era, used both as the home-screen card icon and the detail-page
        # banner.
        for era in rows:
            fields = []
            if url is not None and era.logo_url != url:
                era.logo_url = url
                fields.append("logo_url")
            if url is not None and era.symbol_url != url:
                era.symbol_url = url
                fields.append("symbol_url")
            if not fields:
                continue
            era.save(update_fields=fields)
            updated_rows += 1
            print(f"    saved on Era(code={era.code!r}, name={era.name!r}): {', '.join(fields)}")

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
