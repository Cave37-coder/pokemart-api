import pandas as pd

MAPPING = {
    "sv1": "SV1", "sv2": "SV2", "sv3": "SV3", "sv3pt5": "SV3PT5",
    "sv4": "SV4", "sv4pt5": "SV4PT5", "sv5": "TEF", "sv6": "TWM",
    "sv6pt5": "SFA", "sv7": "SCR", "sv8": "SSP", "sv8pt5": "PRE",
    "sv9": "JTG",
    "swsh1": "SSH", "swsh2": "RCL", "swsh3": "DAA", "swsh4": "VIV",
    "swsh5": "BST", "swsh6": "CRE", "swsh8": "FUS", "swsh9": "BRS",
    "swsh10": "ASR", "swsh11": "LOR", "swsh12": "SIT",
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
    "col1": "CL", "me1": "MEG", "me2": "POR", "me2pt5": "CHP",
    "cel25": "CEL", "cel25c": "CELCC",
    "pgo": "PGO", "dc1": "DCR", "det1": "DET",
}
VMAP = {"norm": "N", "rev": "RH", "holo": "H", "1sted": "1E"}

df = pd.read_csv("stock.csv", usecols=["sku","quantity","price"])
df["prefix"] = df["sku"].str.extract(r"^([a-z0-9]+)-\d+")
df["card_num"] = df["sku"].str.extract(r"^[a-z0-9]+-(\d+)").astype(float)
df["var_raw"] = df["sku"].str.extract(r"^[a-z0-9]+-\d+-(.+)$")[0]
df["db_code"] = df["prefix"].map(MAPPING)
df["variant"] = df["var_raw"].map(VMAP)
df = df[df["db_code"].notna() & df["variant"].notna() & (df["quantity"] > 0)]

print("Sample unmatched SKUs by set:")
for code in df["db_code"].unique()[:10]:
    sample = df[df["db_code"] == code]["sku"].head(3).tolist()
    print(f"  {code}: {sample}")
