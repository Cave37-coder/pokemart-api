"""
upload_energy_symbols.py

Uploads the 11 energy-type symbol PNGs from the local folder to R2, at
energy-types/, matching the exact filenames stock_dividers() expects.

Credentials are read from environment variables -- nothing sensitive is
hardcoded in this file. Set these in PowerShell before running:

    $env:R2_ACCOUNT_ID = "your-cloudflare-account-id"
    $env:R2_ACCESS_KEY_ID = "your-r2-access-key-id"
    $env:R2_SECRET_ACCESS_KEY = "your-r2-secret-access-key"

Then run:

    python upload_energy_symbols.py            # uploads for real
    python upload_energy_symbols.py --dry-run  # just lists what would upload

Bucket name and local folder are set as constants below -- adjust if either
ever changes.
"""

import os
import sys
import boto3
from botocore.config import Config

BUCKET_NAME = "pokebulkcards"
LOCAL_FOLDER = r"C:\Users\texca\pokemart-api\media\card_images\Energy Symbols"
R2_PREFIX = "energy-types/"

# (local filename on disk, R2 key to upload as)
# Local files use spaces; R2 keys use underscores to match TYPE_IMG_FILE
# in products/views.py exactly, so no code changes are needed there.
FILES = [
    ("Dragon Energy Symbol.png", "Dragon_Energy_Symbol.png"),
    ("Electric Energy Symbol.png", "Electric_Energy_Symbol.png"),
    ("Fairy Energy Symbol.png", "Fairy_Energy_Symbol.png"),
    ("Fighting Energy Symbol.png", "Fighting_Energy_Symbol.png"),
    ("Fire Energy Symbol.png", "Fire_Energy_Symbol.png"),
    ("Leaf Energy Symbol.png", "Leaf_Energy_Symbol.png"),
    ("Metal energy Symbol.png", "Metal_energy_Symbol.png"),
    ("Physic Energy Symbol.png", "Physic_Energy_Symbol.png"),
    ("Water Energy Symbol.png", "Water_Energy_Symbol.png"),
    ("Colorless Energy Symbol.png", "Colorless_Energy_Symbol.png"),
    ("Darkeness energy Symbol.png", "Darkeness_energy_Symbol.png"),
]


def get_client():
    account_id = os.environ.get("R2_ACCOUNT_ID")
    access_key = os.environ.get("R2_ACCESS_KEY_ID")
    secret_key = os.environ.get("R2_SECRET_ACCESS_KEY")

    missing = [name for name, val in [
        ("R2_ACCOUNT_ID", account_id),
        ("R2_ACCESS_KEY_ID", access_key),
        ("R2_SECRET_ACCESS_KEY", secret_key),
    ] if not val]
    if missing:
        print(f"Missing required environment variable(s): {', '.join(missing)}")
        print("Set them in PowerShell first, e.g.:")
        print('  $env:R2_ACCOUNT_ID = "..."')
        sys.exit(1)

    endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def main():
    dry_run = "--dry-run" in sys.argv

    missing_local = []
    for local_name, r2_key in FILES:
        local_path = os.path.join(LOCAL_FOLDER, local_name)
        if not os.path.isfile(local_path):
            missing_local.append(local_path)

    if missing_local:
        print("These files were not found locally -- check the folder path and filenames:")
        for p in missing_local:
            print(f"  MISSING: {p}")
        print()

    to_upload = [(n, k) for n, k in FILES if os.path.isfile(os.path.join(LOCAL_FOLDER, n))]

    if dry_run:
        print(f"[DRY RUN] Would upload {len(to_upload)} file(s) to "
              f"bucket '{BUCKET_NAME}' under '{R2_PREFIX}':")
        for local_name, r2_key in to_upload:
            print(f"  {local_name}  ->  {R2_PREFIX}{r2_key}")
        print("\nRe-run without --dry-run to actually upload.")
        return

    client = get_client()

    print(f"Uploading {len(to_upload)} file(s) to bucket '{BUCKET_NAME}'...\n")
    ok_count = 0
    for local_name, r2_key in to_upload:
        local_path = os.path.join(LOCAL_FOLDER, local_name)
        key = f"{R2_PREFIX}{r2_key}"
        try:
            client.upload_file(
                local_path,
                BUCKET_NAME,
                key,
                ExtraArgs={"ContentType": "image/png"},
            )
            print(f"  OK    {local_name} -> {key}")
            ok_count += 1
        except Exception as e:
            print(f"  FAIL  {local_name}: {e}")

    print(f"\nDone. {ok_count}/{len(to_upload)} uploaded successfully.")
    if ok_count:
        print("\nVerify at, e.g.:")
        print(f"  https://images.pokebulk.co.za/{R2_PREFIX}{to_upload[0][1]}")


if __name__ == "__main__":
    main()
