# upload_30th_logo.py
# One-off: uploads the 30th Celebration gold logo badge to R2 and sets
# CardSet.logo_url for 30C and 30CC only. Does NOT touch symbol_url (left
# blank on purpose -- no small TCG expansion-mark icon exists yet), and does
# NOT touch any other set (unlike upload_set_images.py's MEG-era "force"
# re-sync, which would also re-upload PFL/ASC/CRI/POR/PBL/MEG's images).
#
# Run from: pokemart-api folder
# Command:  python upload_30th_logo.py
#           python upload_30th_logo.py --dry-run

import os, sys, argparse, boto3
from pathlib import Path
from botocore.config import Config

LOCAL_FILE = Path("D:/D Downs/Card Pics/Set Symbols/ERA/thirty.png")
R2_BUCKET = "pokebulkcards"
R2_CDN = "https://images.pokebulk.co.za"
SET_CODES = ["30C", "30CC"]


def get_r2_client():
    return boto3.client(
        "s3",
        endpoint_url="https://229506129ad4206787dd4d3227608e17.r2.cloudflarestorage.com",
        aws_access_key_id="fdff88cee69c515cf67d4ae275d1bc72",
        aws_secret_access_key="e7122d20bd2ad8121756a86f4165af40be5fd3efe40fbdca5f5ca922bb1ace8f",
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not LOCAL_FILE.exists():
        print(f"ERROR: file not found: {LOCAL_FILE}")
        return

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    sys.path.insert(0, str(Path(__file__).parent))
    import django
    django.setup()
    from products.models import CardSet

    sets = {cs.code: cs for cs in CardSet.objects.filter(code__in=SET_CODES)}
    missing = [c for c in SET_CODES if c not in sets]
    if missing:
        print(f"ERROR: CardSet(s) not found in DB: {missing}")
        return

    if not args.dry_run:
        s3 = get_r2_client()
        with open(LOCAL_FILE, "rb") as f:
            data = f.read()

    for code in SET_CODES:
        r2_key = f"sets/logos/{code}_logo.png"
        url = f"{R2_CDN}/{r2_key}"
        if args.dry_run:
            print(f"  [DRY] {code}: would upload {LOCAL_FILE.name} -> {r2_key}, set logo_url = {url}")
            continue
        s3.put_object(Bucket=R2_BUCKET, Key=r2_key, Body=data, ContentType="image/png")
        cs = sets[code]
        cs.logo_url = url
        cs.save(update_fields=["logo_url"])
        print(f"  \u2713 {code} logo_url -> {url}")

    print("\nDone." if not args.dry_run else "\nDry run only -- no changes made.")


if __name__ == "__main__":
    main()
