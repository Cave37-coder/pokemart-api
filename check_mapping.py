import pandas as pd, os, sys, django
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
sys.path.insert(0, ".")
django.setup()

from products.models import CardSet

# TCGPlayer prefix -> DB code mapping
MAPPING = {
    "sv1": "SVI", "sv2": "PAL", "sv3": "OBF", "sv3pt5": "MEW",
    "sv4": "PAR", "sv4pt5": "PAF", "sv5": "TEF", "sv6": "TWM",
    "sv6pt5": "SFA", "sv7": "SCR", "sv8": "SSP", "sv8pt5": "PRI",
    "sv9": "JTG",
    "swsh1": "SWSH", "swsh2": "RCL", "swsh3": "DAA", "swsh4": "VIV",
    "swsh4pt5": "SWSH45", "swsh5": "BST", "swsh6": "CRE", "swsh7": "EVO",
    "swsh8": "FUS", "swsh9": "BRS", "swsh10": "ASR", "swsh11": "LOR",
    "swsh12": "SIT", "swsh12pt5": "SIT125",
    "sm1": "SUM", "sm2": "GRI", "sm3": "BUS", "sm3pt5": "SLG",
    "sm4": "CIN", "sm5": "UPR", "sm6": "FLI", "sm7": "CES",
    "sm7a": "DRM", "sm8": "LOT", "sm9": "TEU", "sm10": "UNB",
    "sm11": "UNM", "sm11a": "HIF", "sm12": "CEC",
    "bw1": "BLW", "bw2": "EPO", "bw3": "NXD", "bw4": "NVI",
    "bw5": "NDE", "bw6": "DEX", "bw7": "DRX", "bw8": "BCR",
    "bw9": "PLS", "bw10": "PLF", "bw11": "PLB", "bw12": "LTR",
    "xy1": "XY", "xy2": "FLF", "xy3": "FFI", "xy4": "PHF",
    "xy5": "PRC", "xy6": "ROS", "xy7": "AOR", "xy8": "BKT",
    "xy9": "BKP", "xy10": "FCO", "xy11": "STS", "xy12": "EVO",
    "g1": "G1", "g2": "G2",
    "hgss1": "HS", "hgss2": "UL", "hgss3": "UD", "hgss4": "TM",
    "col1": "CL",
    "me1": "MEG", "me2": "POR", "me2pt5": "CHP",
    "cel25": "CEL", "cel25c": "CELCC",
    "pgo": "PGO", "dc1": "DC1", "det1": "DET", "dv1": "DV1",
    "ru1": "RU1", "rsv10pt5": "SFA",
}

df = pd.read_csv("store_data_20260518_140458.csv", usecols=["sku","quantity","price"])
df["prefix"] = df["sku"].str.extract(r"^([a-z0-9]+)-\d+")
df["db_code"] = df["prefix"].map(MAPPING)

matched = df[df["db_code"].notna()]
unmatched_prefixes = df[df["db_code"].isna()]["prefix"].dropna().unique()

print(f"Total CSV rows: {len(df):,}")
print(f"Matched rows: {len(matched):,}")
print(f"Unmatched prefixes: {sorted(unmatched_prefixes)}")
