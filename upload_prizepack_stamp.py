"""
Uploads the Play! Pokemon program stamp icon to R2.

Save prizepack_stamp.webp into this folder (C:\\Users\\texca\\pokemart-api)
before running, or edit LOCAL_PATH below to point at wherever you saved it.

Run:
    python upload_prizepack_stamp.py
"""
import boto3
from pathlib import Path
from botocore.config import Config

LOCAL_PATH = Path(r"D:\D Downs\Pokemon Junk\prize pack stamp.png")

R2_ACCESS_KEY_ID = "fdff88cee69c515cf67d4ae275d1bc72"
R2_SECRET_ACCESS_KEY = "e7122d20bd2ad8121756a86f4165af40be5fd3efe40fbdca5f5ca922bb1ace8f"
R2_ENDPOINT = "https://229506129ad4206787dd4d3227608e17.r2.cloudflarestorage.com"
R2_BUCKET = "pokebulkcards"
PUBLIC_URL = "https://images.pokebulk.co.za"
R2_KEY = "sets/symbols/prizepack_stamp.png"

s3 = boto3.client(
    "s3",
    endpoint_url=R2_ENDPOINT,
    aws_access_key_id=R2_ACCESS_KEY_ID,
    aws_secret_access_key=R2_SECRET_ACCESS_KEY,
    config=Config(signature_version="s3v4"),
    region_name="auto",
)

if not LOCAL_PATH.exists():
    print(f"!! File not found: {LOCAL_PATH.resolve()}")
    print("   Save prizepack_stamp.webp here, or edit LOCAL_PATH at the top of this script.")
else:
    with open(LOCAL_PATH, "rb") as f:
        data = f.read()
    s3.put_object(Bucket=R2_BUCKET, Key=R2_KEY, Body=data, ContentType="image/png")
    url = f"{PUBLIC_URL}/{R2_KEY}"
    print(f"Uploaded successfully.")
    print(f"URL: {url}")
