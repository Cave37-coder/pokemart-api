"""
Quick patch to fix rarity casing in download_card_images.
Replaces the clean_rarity function to handle lowercase DB values.

    cd C:\\Users\\texca\\pokemart-api
    python patch_rarity_case.py
"""

import os

PATH = os.path.join("products", "management", "commands", "download_card_images.py")

with open(PATH, "r", encoding="utf-8") as fh:
    content = fh.read()

OLD = '''def clean_rarity(rarity):
    """Return a filename-safe rarity label."""
    if not rarity:
        return ""
    return RARITY_CLEAN.get(rarity, re.sub(r"[^\\w-]", "-", rarity).strip("-"))'''

NEW = '''def clean_rarity(rarity):
    """Return a filename-safe rarity label.
    Handles both title-case ('Rare Holo') and lowercase ('rare holo') DB values.
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

if OLD in content:
    content = content.replace(OLD, NEW)
    with open(PATH, "w", encoding="utf-8") as fh:
        fh.write(content)
    print(f"✓ Patched: {PATH}")
    print()
    print("Dry run to verify:")
    print("  python manage.py download_card_images --dry-run 2>&1 | findstr DRY | findstr BS-00")
    print()
    print("You should now see:")
    print("  WotC/BS-001-Alakazam-Holo-Rare.png")
    print("  WotC/BS-017-Beedrill-Rare.png")
    print("  WotC/BS-023-Arcanine-Uncommon.png")
    print("  WotC/BS-058-Pikachu-Common.png")
else:
    print("✗ Could not find the clean_rarity function to patch.")
    print("  The function may have already been updated or the file structure changed.")
    print("  Check the file manually: products/management/commands/download_card_images.py")
