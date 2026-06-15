"""
Patch download_card_images to organise images into set subfolders within era folders.

    cd C:\\Users\\texca\\pokemart-api
    python patch_set_subfolders.py

Before: media/card_images/originals/WotC/BS-001-Alakazam-Holo-Rare.png
After:  media/card_images/originals/WotC/BS/BS-001-Alakazam-Holo-Rare.png
"""

import os

PATH = os.path.join("products", "management", "commands", "download_card_images.py")

with open(PATH, "r", encoding="utf-8") as fh:
    content = fh.read()

OLD = '''            era      = get_era(sc)
            filename = make_filename(sc, num, name, rarity)
            dest_dir  = base_dir / era
            dest_file = dest_dir / filename'''

NEW = '''            era      = get_era(sc)
            filename = make_filename(sc, num, name, rarity)
            dest_dir  = base_dir / era / sc   # era/SET/filename.png
            dest_file = dest_dir / filename'''

if OLD in content:
    content = content.replace(OLD, NEW)
    with open(PATH, "w", encoding="utf-8") as fh:
        fh.write(content)
    print(f"✓ Patched: {PATH}")
    print()
    print("Structure will now be:")
    print("  media/card_images/originals/WotC/BS/BS-001-Alakazam-Holo-Rare.png")
    print("  media/card_images/originals/MEG-Era/PFL/PFL-001-Oddish-Common.png")
    print("  media/card_images/originals/SV-Era/SCR/SCR-001-Venusaur-ex-Double-Rare.png")
    print()
    print("Verify:")
    print("  python manage.py download_card_images --set BS --dry-run")
else:
    print("✗ Could not find the dest_dir line to patch.")
    print("  Open the file and manually change:")
    print("    dest_dir  = base_dir / era")
    print("  to:")
    print("    dest_dir  = base_dir / era / sc")
