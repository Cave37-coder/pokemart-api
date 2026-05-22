"""
Patches download_card_images to fix:
  1. Strip variant suffixes from product names  e.g. 'Oddish (Reverse Holo)' → 'Oddish'
  2. Fix rarity casing  e.g. 'ultra_rare' → 'Ultra-Rare', 'common' → 'Common'

    cd C:\\Users\\texca\\pokemart-api
    python patch_name_rarity.py
"""

import os

PATH = os.path.join("products", "management", "commands", "download_card_images.py")

with open(PATH, "r", encoding="utf-8") as fh:
    content = fh.read()

# ── 1. Replace clean_rarity with one that handles DB format ──────────────────
OLD_RARITY = '''def clean_rarity(rarity):
    """Return a filename-safe rarity label.
    Handles both title-case (\'Rare Holo\') and lowercase (\'rare holo\') DB values.
    """
    if not rarity:
        return ""

    # Build a case-insensitive lookup the first time
    rarity_stripped = rarity.strip()

    # Direct match first
    if rarity_stripped in RARITY_CLEAN:
        return RARITY_CLEAN[rarity_stripped]

    # Case-insensitive match
    lower = rarity_stripped.lower()
    for key, val in RARITY_CLEAN.items():
        if key.lower() == lower:
            return val

    # Fallback: title-case it, replace spaces/underscores with hyphens
    import re as _re
    cleaned = rarity_stripped.replace("_", " ").title()
    return _re.sub(r"[^\\w-]", "-", cleaned).strip("-")'''

NEW_RARITY = '''# DB stores rarities as lowercase_underscore — map to clean labels
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
    r"\\s*\\(Reverse Holo\\)$",
    r"\\s*\\(Normal\\)$",
    r"\\s*\\(Holofoil\\)$",
    r"\\s*\\(Holo\\)$",
    r"\\s*\\(1st Edition\\)$",
    r"\\s*\\(First Edition\\)$",
    r"\\s*\\(Mirror Holo\\)$",
    r"\\s*\\(ETB Reverse Holo\\)$",
    r"\\s*\\(Ace Spec\\)$",
    r"\\s*\\(Poké Ball Holo\\)$",
    r"\\s*\\(Master Ball Holo\\)$",
    r"\\s*\\(Fast Ball Holo\\)$",
    r"\\s*\\(Luxury Ball Holo\\)$",
    r"\\s*\\(Quick Ball Holo\\)$",
    r"\\s*\\(Dusk Ball Holo\\)$",
    r"\\s*\\(Rocket Ball Holo\\)$",
    r"\\s*\\(Love Ball Holo\\)$",
    r"\\s*\\(Friend Ball Holo\\)$",
    r"\\s*\\(Energy Holo\\)$",
    # Generic fallback — anything in parentheses at the end
    r"\\s*\\([^)]+\\)$",
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
    return cleaned.strip() or "Unknown"'''

# ── 2. Fix the work-building block to use clean_card_name ────────────────────
OLD_WORK = '''        # Deduplicate: one image per (set_code, card_number)
        work = {}
        for row in qs:
            sc     = row["card_set__code"]
            num    = row["card_number"]
            name   = row["name"] or "Unknown"
            rarity = row["rarity"] or ""
            if sc and num:
                key = f"{sc}:{num}"
                if key not in work:
                    work[key] = (sc, num, name, rarity)'''

NEW_WORK = '''        # Deduplicate: one image per (set_code, card_number)
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
                    work[key] = (sc, num, name, rarity)'''

# Apply patches
patched = False

if OLD_RARITY in content:
    content = content.replace(OLD_RARITY, NEW_RARITY)
    print("✓ Patched: clean_rarity + clean_card_name functions")
    patched = True
else:
    # Try to inject before class Command
    if "def clean_rarity" in content:
        # Replace just the function body
        import re
        content = re.sub(
            r'def clean_rarity\(rarity\):.*?(?=\ndef |\nclass )',
            NEW_RARITY + "\n\n",
            content,
            flags=re.DOTALL
        )
        print("✓ Patched: clean_rarity replaced (regex method)")
        patched = True
    else:
        # Inject before class Command
        content = content.replace(
            "class Command(BaseCommand):",
            NEW_RARITY + "\n\n\nclass Command(BaseCommand):"
        )
        print("✓ Injected: clean_rarity + clean_card_name before Command class")
        patched = True

if OLD_WORK in content:
    content = content.replace(OLD_WORK, NEW_WORK)
    print("✓ Patched: work-building block uses clean_card_name")
else:
    # Fallback — patch just the name line
    old_name = '            name   = row["name"] or "Unknown"'
    new_name = '            name   = clean_card_name(row["name"] or "")'
    if old_name in content:
        content = content.replace(old_name, new_name)
        print("✓ Patched: name line uses clean_card_name (fallback)")
    else:
        print("⚠  Could not patch work block — check file manually")

if patched:
    with open(PATH, "w", encoding="utf-8") as fh:
        fh.write(content)
    print()
    print("Done. Verify with:")
    print("  python manage.py download_card_images --set PFL --dry-run")
    print()
    print("You should see:")
    print("  MEG-Era/PFL-001-Oddish-Common.png           (not 'Oddish-Reverse-Holo-Common')")
    print("  MEG-Era/PFL-004-Mega-Heracross-ex-Ultra-Rare.png")
    print("  MEG-Era/PFL-054-Gastly-Common.png           (was failing before)")
    print()
    print("Then resume the full download (skips already-downloaded):")
    print("  python manage.py download_card_images")
