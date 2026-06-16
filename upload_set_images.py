# upload_set_images.py
# Uploads set logos and symbols from local folder to R2,
# then updates Railway DB with the CDN URLs.
# Run from: pokemart-api folder
# Command:  python upload_set_images.py

import os, sys, boto3
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
SYMBOLS_DIR = Path("D:/D Downs/Card Pics/Set Symbols")
R2_BUCKET   = "pokebulkcards"
R2_CDN      = "https://images.pokebulk.co.za"

# ── Mapping: DB code → (logo_filename, symbol_filename)
# logo  = horizontal banner image (e.g. SV1_Logo_EN.png)
# symbol = small set icon (e.g. SetSymbolScarlet_and_Violet.png)
# Set to None if not available
SET_MAP = {
    # ── Scarlet & Violet ──────────────────────────────────────────────────────
    "SVI":    ("SV1_Logo_EN.png",               "SetSymbolScarlet_and_Violet.png"),
    "PAL":    ("SV2_Logo_EN.png",               "SetSymbolPaldea_Evolved.png"),
    "OBF":    ("SV3_Logo_EN.png",               "SetSymbolObsidian_Flames.png"),
    "MEW":    ("SV3.5_Logo_EN.png",             "SetSymbol151.png"),
    "PAR":    ("SV4_Logo_EN.png",               "SetSymbolParadox_Rift.png"),
    "PAF":    ("SV4.5_Logo_EN.png",             "SetSymbolPaldean_Fates.png"),
    "TEF":    ("SV5_Logo_EN.png",               "SetSymbolTemporal_Forces.png"),
    "TWM":    ("SV6_Logo_EN.png",               "SetSymbolTwilight_Masquerade.png"),
    "SFA":    ("SV6.5_Logo_EN.png",             "SetSymbolShrouded_Fable.png"),
    "SCR":    ("SV7_Logo_EN.png",               "SetSymbolStellar_Crown.png"),
    "SSP":    ("SV8_Logo_EN.png",               "SetSymbolSurging_Sparks.png"),
    "PRE":    ("1920px-SV8.5_Logo_EN.png",      "SetSymbolPrismatic_Evolutions.png"),
    "JTG":    ("1920px-SV9_Logo_EN.png",        "SetSymbolJourney_Together.png"),
    "TEF":    ("SV5_Logo_EN.png",               "SetSymbolTemporal_Forces.png"),
    "BLK":    ("SV10.5_BLK_Logo_EN.png",        "SetSymbolBlack_Bolt.png"),
    "WHT":    ("SV10.5_WHT_Logo_EN.png",        "SetSymbolWhite_Flare.png"),
    "DRI":    ("SV10_Logo_EN.png",              "SetSymbolDestined_Rivals.png"),
    "SVE":    (None,                             "SetSymbolSVE_Basic_Energies.png"),
    "SVP":    (None,                             "SetSymbolSVP_Black_Star_Promos.png"),

    # ── Sword & Shield ────────────────────────────────────────────────────────
    "SSH":    ("SWSH1_Logo_EN.png",             "SetSymbolSword_and_Shield.png"),
    "RCL":    ("SWSH2_Logo_EN.png",             "SetSymbolRebel_Clash.png"),
    "DAA":    ("SWSH3_Logo_EN.png",             "SetSymbolDarkness_Ablaze.png"),
    "VIV":    ("SWSH4_Logo_EN.png",             "SetSymbolVivid_Voltage.png"),
    "SHF":    ("Shining_Fates_Logo_EN.png",     "SetSymbolShining_Fates.png"),
    "BST":    ("SWSH5_Logo_EN.png",             "SetSymbolBattle_Styles.png"),
    "CRE":    ("SWSH6_Logo_EN.png",             "SetSymbolChilling_Reign.png"),
    "EVS":    ("SWSH7_Logo_EN.png",             "SetSymbolEvolving_Skies.png"),
    "CEL":    ("Celebrations_Logo_EN.png",      "SetSymbolCelebrations.png"),
    "FST":    ("SWSH8_Logo_EN.png",             "SetSymbolFusion_Strike.png"),
    "BRS":    ("SWSH9_Logo_EN.png",             "SetSymbolBrilliant_Stars.png"),
    "ASR":    ("SWSH10_Logo_EN.png",            "SetSymbolAstral_Radiance.png"),
    "PGO":    ("Pokemon_Go_Logo.png",           "SetSymbolPokémon_GO.png"),
    "LOR":    ("SWSH11_Logo_EN.png",            "SetSymbolLost_Origin.png"),
    "SIT":    ("SWSH12_Logo_EN.png",            "SetSymbolSilver_Tempest.png"),
    "CRZ":    ("Crown_Zenith_Logo_EN.png",      "SetSymbolCrown_Zenith.png"),
    "CHP":    ("Champion_Path_Logo_EN.png",     "SetSymbolChampion_Path.png"),
    "SWSH05": ("SWSH5_Logo_EN.png",             "SetSymbolBattle_Styles.png"),

    # ── Sun & Moon ────────────────────────────────────────────────────────────
    "SM01":   ("SM1_Logo_EN.png",               "SetSymbolSun_and_Moon.png"),
    "SM02":   ("SM2_Logo_EN.png",               "SetSymbolGuardians_Rising.png"),
    "SM03":   ("SM3_Logo_EN.png",               "SetSymbolBurning_Shadows.png"),
    "SM04":   ("SM4_Logo_EN.png",               "SetSymbolCrimson_Invasion.png"),
    "SM05":   ("SM5_Logo_EN.png",               "SetSymbolUltra_Prism.png"),
    "SM06":   ("SM6_Logo_EN.png",               "SetSymbolForbidden_Light.png"),
    "SM8":    ("SM8_Logo_EN.png",               "SetSymbolLost_Thunder.png"),
    "SM9":    ("SM9_Logo_EN.png",               "SetSymbolTeam_Up.png"),
    "SM10":   ("SM10_Logo_EN.png",              "SetSymbolUnbroken_Bonds.png"),
    "SM11":   ("SM11_Logo_EN.png",              "SetSymbolUnified_Minds.png"),
    "SM12":   ("SM12_Logo_EN.png",              "SetSymbolCosmic_Eclipse.png"),
    "SHL":    ("Shining_Legends_Logo_EN.png",   "SetSymbolShining_Legends.png"),
    "DRM":    ("Dragon_Majesty_Logo_EN.png",    "SetSymbolDragon_Majesty.png"),
    "HIF":    ("Hidden_Fates_Logo_EN.png",      "SetSymbolHidden_Fates.png"),
    "CES":    ("SM7_Logo_EN.png",               "SetSymbolCelestial_Storm.png"),
    "SMP":    (None,                             "SetSymbolPromo.png"),

    # ── Mega Evolution ────────────────────────────────────────────────────────
    "MEG":    ("ME1_Logo_EN.png",               "SetSymbolMega_Evolution.png"),
    "PFL":    ("ME2_Logo_EN.png",               "SetSymbolPhantasmal_Flames.png"),
    "ASC":    ("1920px-ME2.5_Logo_EN.png",      "SetSymbolAscended_Heroes.png"),
    "CRI":    ("ME4_Logo_EN.png",               "SetSymbolChaos_Rising.png"),
    "POR":    ("ME3_Logo_EN.png",               "SetSymbolPerfect_Order.png"),
    "PBL":    (None,                             "SetSymbolPitch_Black.png"),
    "RUM":    ("1920px-Pokémon_Rumble_logo.png","SetSymbolPokémon_Rumble.png"),

    # ── HGSS ─────────────────────────────────────────────────────────────────
    "HS":     ("HS1_Logo_EN.png",               "SetSymbolHeartGold_and_SoulSilver.png"),
    "UL":     ("HS2_Logo_EN.png",               "SetSymbolUnleashed.png"),
    "UD":     ("HS3_Logo_EN.png",               "SetSymbolUndaunted.png"),
    "TM":     ("HS4_Logo_EN.png",               "SetSymbolTriumphant.png"),
    "CoL":    ("COL1_Logo_EN.png",              "SetSymbolCall_of_Legends.png"),

    # ── Trick or Trade ────────────────────────────────────────────────────────
    "TT22":   ("Trick_or_Trade.png",            None),
    "TT23":   ("Trick_or_Trade_2023.png",       None),
    "TT24":   ("Trick_or_Trade_2024.png",       None),
}


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
    """Search for filename in root and all subdirectories."""
    if not filename:
        return None
    # Check root first
    p = SYMBOLS_DIR / filename
    if p.exists():
        return p
    # Search subdirs
    for f in SYMBOLS_DIR.rglob(filename):
        return f
    return None


def upload_file(s3, local_path, r2_key):
    with open(str(local_path), "rb") as f:
        data = f.read()
    s3.put_object(
        Bucket=R2_BUCKET,
        Key=r2_key,
        Body=data,
        ContentType="image/png",
    )
    return f"{R2_CDN}/{r2_key}"


def main():
    # Setup Django
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    sys.path.insert(0, str(Path(__file__).parent))
    import django
    django.setup()
    from products.models import CardSet

    s3 = get_r2_client()
    updated = 0
    skipped = 0
    missing_file = []

    sets = CardSet.objects.all()
    set_by_code = {s.code: s for s in sets}

    for code, (logo_fn, symbol_fn) in SET_MAP.items():
        cs = set_by_code.get(code)
        if not cs:
            print(f"  SKIP {code} — not in DB")
            skipped += 1
            continue

        changed = False
        force = cs.era and cs.era.code == 'MEG'

        # Upload logo
        if logo_fn and (not cs.logo_url or force):
            local = find_file(logo_fn)
            if local:
                r2_key = f"sets/logos/{code}_logo.png"
                url = upload_file(s3, local, r2_key)
                cs.logo_url = url
                changed = True
                print(f"  ✓ {code} logo → {url}")
            else:
                missing_file.append(f"{code} logo: {logo_fn}")
                print(f"  ✗ {code} logo file not found: {logo_fn}")

        # Upload symbol
        if symbol_fn and (not cs.symbol_url or force):
            local = find_file(symbol_fn)
            if local:
                r2_key = f"sets/symbols/{code}_symbol.png"
                url = upload_file(s3, local, r2_key)
                cs.symbol_url = url
                changed = True
                print(f"  ✓ {code} symbol → {url}")
            else:
                missing_file.append(f"{code} symbol: {symbol_fn}")
                print(f"  ✗ {code} symbol file not found: {symbol_fn}")

        if changed:
            cs.save(update_fields=["logo_url", "symbol_url"])
            updated += 1
        else:
            if cs.logo_url and cs.symbol_url:
                print(f"  — {code} already has logo+symbol, skipping")
            skipped += 1

    print(f"\nDone — {updated} sets updated, {skipped} skipped")
    if missing_file:
        print(f"\nMissing files ({len(missing_file)}):")
        for m in missing_file:
            print(f"  {m}")


if __name__ == "__main__":
    main()
