import subprocess
import sys

# All missing sets grouped by era
MISSING_SETS = [
    # B2 - EX Era
    ("ex1", "EX Ruby & Sapphire"),
    ("ex2", "EX Sandstorm"),
    ("ex3", "EX Dragon"),
    ("ex4", "EX Team Magma vs Team Aqua"),
    ("ex5", "EX Hidden Legends"),
    ("ex6", "EX FireRed & LeafGreen"),
    ("ex7", "EX Team Rocket Returns"),
    ("ex8", "EX Deoxys"),
    ("ex9", "EX Emerald"),
    ("ex10", "EX Unseen Forces"),
    ("ex11", "EX Delta Species"),
    ("ex12", "EX Legend Maker"),
    ("ex13", "EX Holon Phantoms"),
    ("ex14", "EX Crystal Guardians"),
    ("ex15", "EX Dragon Frontiers"),
    ("ex16", "EX Power Keepers"),

    # B5 - XY (missing sets)
    ("xy2", "XY—Flashfire"),
    ("xy3", "XY—Furious Fists"),  # already have FFI? check
    ("xy4", "XY—Phantom Forces"),
    ("xy5", "XY—Primal Clash"),
    ("xy6", "XY—Roaring Skies"),
    ("xy7", "XY—Ancient Origins"),
    ("xy8", "XY—BREAKthrough"),
    ("xy9", "XY—BREAKpoint"),
    ("xy10", "XY—Fates Collide"),
    ("xy11", "XY—Steam Siege"),
    ("xy12", "XY—Evolutions"),
    ("xyp", "XY—Black Star Promos"),
    ("g1", "Generations"),

    # B6 - Sun & Moon
    ("sm1", "Sun & Moon"),
    ("sm2", "Guardians Rising"),
    ("sm3", "Burning Shadows"),
    ("sm35", "Shining Legends"),
    ("sm4", "Crimson Invasion"),
    ("sm5", "Ultra Prism"),
    ("sm6", "Forbidden Light"),
    ("sm7", "Celestial Storm"),
    ("sm75", "Dragon Majesty"),
    ("sm8", "Lost Thunder"),
    ("sm9", "Team Up"),
    ("sm10", "Unbroken Bonds"),
    ("sm11", "Unified Minds"),
    ("sm115", "Hidden Fates"),
    ("sm12", "Cosmic Eclipse"),
    ("smp", "SM—Black Star Promos"),

    # B7 - Sword & Shield
    ("swsh1", "Sword & Shield"),
    ("swsh2", "Rebel Clash"),
    ("swsh3", "Darkness Ablaze"),
    ("swsh35", "Champion's Path"),
    ("swsh4", "Vivid Voltage"),
    ("swsh45", "Shining Fates"),
    ("swsh5", "Battle Styles"),
    ("swsh6", "Chilling Reign"),
    ("swsh7", "Evolving Skies"),
    ("swsh8", "Fusion Strike"),
    ("swsh9", "Brilliant Stars"),
    ("swsh10", "Astral Radiance"),
    ("swsh11", "Lost Origin"),
    ("swsh12", "Silver Tempest"),
    ("swsh12pt5", "Crown Zenith"),
    ("swshp", "SWSH—Black Star Promos"),

    # B8 - Scarlet & Violet
    ("sv1", "Scarlet & Violet"),
    ("sv2", "Paldea Evolved"),
    ("sv3", "Obsidian Flames"),
    ("sv3pt5", "151"),
    ("sv4", "Paradox Rift"),
    ("sv4pt5", "Paldean Fates"),
    ("sv5", "Temporal Forces"),
    ("sv6", "Twilight Masquerade"),
    ("sv6pt5", "Shrouded Fable"),
    ("sv7", "Stellar Crown"),
    ("sv8", "Surging Sparks"),
    ("sv8pt5", "Prismatic Evolutions"),
    ("svp", "SV—Black Star Promos"),

    # ME - Mega Era (fan sets)
    ("me2pt5", "Ascended Heroes"),
    ("me03", "Perfect Order"),
]

print(f"Total sets to import: {len(MISSING_SETS)}")
print("Starting batch import...\n")

failed = []
for set_id, set_name in MISSING_SETS:
    print(f"{'='*50}")
    print(f"Importing: {set_name} ({set_id})")
    result = subprocess.run(
        [sys.executable, "manage.py", "enrich_set", set_id],
        cwd=r"C:\Users\texca\pokemart-api",
        capture_output=False,
        text=True
    )
    if result.returncode != 0:
        print(f"FAILED: {set_id}")
        failed.append((set_id, set_name))

print(f"\n{'='*50}")
print(f"Done! Failed sets: {failed if failed else 'None'}")
