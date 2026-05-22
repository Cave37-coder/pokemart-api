"""
pokemon.com checklist PDF URLs mapped to Pokémon TCG API set codes.
Use CardSet.code (which matches the API set id) as the key.

URL base constants:
  OLD  = https://www.pokemon.com/static-assets/content-assets/cms/pdf/tcg/checklists/
  NEW  = https://www.pokemon.com/static-assets/content-assets/cms2/pdf/trading-card-game/checklist/
  ALT  = https://assets.pokemon.com/assets/cms2/pdf/trading-card-game/checklist/
  TCG  = https://tcg.pokemon.com/assets/img/sv-expansions/

Confidence levels:
  CONFIRMED  - URL appeared directly in search results / known working
  INFERRED   - Filename pattern deduced from confirmed neighbours; needs verification
"""

BASE_OLD = "https://www.pokemon.com/static-assets/content-assets/cms/pdf/tcg/checklists/"
BASE_NEW = "https://www.pokemon.com/static-assets/content-assets/cms2/pdf/trading-card-game/checklist/"
BASE_ALT = "https://assets.pokemon.com/assets/cms2/pdf/trading-card-game/checklist/"

CHECKLIST_MAP = {
    # ─── EX Era (2003–2007) ───────────────────────────────────────────────────
    # API series: "EX"
    "ex1":  (BASE_OLD, "rubysapphire_checklist.pdf",         "CONFIRMED"),
    "ex2":  (BASE_OLD, "sandstorm_checklist.pdf",            "INFERRED"),
    "ex3":  (BASE_OLD, "dragon_checklist.pdf",               "INFERRED"),
    "ex4":  (BASE_OLD, "teammagnateamaqua_checklist.pdf",    "INFERRED"),
    "ex5":  (BASE_OLD, "hiddenlegends_checklist.pdf",        "INFERRED"),
    "ex6":  (BASE_OLD, "fireredleafgreen_checklist.pdf",     "CONFIRMED"),
    "ex7":  (BASE_OLD, "teamrocketreturns_checklist.pdf",    "INFERRED"),
    "ex8":  (BASE_OLD, "deoxys_checklist.pdf",               "INFERRED"),
    "ex9":  (BASE_OLD, "emerald_checklist.pdf",              "INFERRED"),
    "ex10": (BASE_OLD, "unseenforces_checklist.pdf",         "INFERRED"),
    "ex11": (BASE_OLD, "deltaspecies_checklist.pdf",         "INFERRED"),
    "ex12": (BASE_OLD, "legendmaker_checklist.pdf",          "INFERRED"),
    "ex13": (BASE_OLD, "holonphantoms_checklist.pdf",        "INFERRED"),
    "ex14": (BASE_OLD, "crystalguardians_checklist.pdf",     "INFERRED"),
    "ex15": (BASE_OLD, "dragonfrontiers_checklist.pdf",      "INFERRED"),
    "ex16": (BASE_OLD, "powerkeepers_checklist.pdf",         "INFERRED"),

    # ─── Diamond & Pearl Era (2007–2009) ─────────────────────────────────────
    # API series: "Diamond & Pearl"
    "dp1":  (BASE_OLD, "DP1_Cardlist_Lo.pdf",  "INFERRED"),
    "dp2":  (BASE_OLD, "DP2_Cardlist_Lo.pdf",  "INFERRED"),
    "dp3":  (BASE_OLD, "DP3_Cardlist_Lo.pdf",  "CONFIRMED"),
    "dp4":  (BASE_OLD, "DP4_Cardlist_Lo.pdf",  "INFERRED"),
    "dp5":  (BASE_OLD, "DP5_Cardlist_Lo.pdf",  "CONFIRMED"),
    "dp6":  (BASE_OLD, "DP6_Cardlist_Lo.pdf",  "INFERRED"),
    "dp7":  (BASE_OLD, "DP7_Cardlist_Lo.pdf",  "INFERRED"),

    # ─── Platinum Era (2009–2010) ─────────────────────────────────────────────
    # API series: "Platinum"
    "pl1":  (BASE_OLD, "PT1_Cardlist_Lo.pdf",  "INFERRED"),
    "pl2":  (BASE_OLD, "PT2_Cardlist_Lo.pdf",  "INFERRED"),
    "pl3":  (BASE_OLD, "PT3_Cardlist_Lo.pdf",  "CONFIRMED"),  # appeared in search
    "pl4":  (BASE_OLD, "PT4_Cardlist_Lo.pdf",  "INFERRED"),

    # ─── HeartGold & SoulSilver Era (2010–2011) ───────────────────────────────
    # API series: "HeartGold & SoulSilver"
    "hgss1": (BASE_ALT, "hgss1_web_cardlist_en.pdf", "CONFIRMED"),
    "hgss2": (BASE_ALT, "hgss2_web_cardlist_en.pdf", "INFERRED"),
    "hgss3": (BASE_ALT, "hgss3_web_cardlist_en.pdf", "INFERRED"),
    "hgss4": (BASE_ALT, "hgss4_web_cardlist_en.pdf", "INFERRED"),
    "col1":  (BASE_ALT, "col_web_cardlist_en.pdf",   "CONFIRMED"),

    # ─── Black & White Era (2011–2013) ───────────────────────────────────────
    # API series: "Black & White"
    "bw1":   (BASE_NEW, "bw1_web_cardlist_en.pdf",   "INFERRED"),
    "bw2":   (BASE_NEW, "bw2_web_cardlist_en.pdf",   "INFERRED"),
    "bw3":   (BASE_NEW, "bw3_web_cardlist_en.pdf",   "INFERRED"),
    "bw4":   (BASE_NEW, "bw4_web_cardlist_en.pdf",   "INFERRED"),
    "bw5":   (BASE_NEW, "bw5_web_cardlist_en.pdf",   "INFERRED"),
    "bw6":   (BASE_NEW, "bw6_web_cardlist_en.pdf",   "INFERRED"),
    "bw6pt5":(BASE_NEW, "bw6pt5_web_cardlist_en.pdf","INFERRED"),
    "bw7":   (BASE_NEW, "bw7_web_cardlist_en.pdf",   "INFERRED"),
    "bw8":   (BASE_NEW, "bw8_web_cardlist_en.pdf",   "INFERRED"),
    "bw9":   (BASE_NEW, "bw9_web_cardlist_en.pdf",   "INFERRED"),
    "bw10":  (BASE_NEW, "bw10_web_cardlist_en.pdf",  "INFERRED"),
    "bw11":  (BASE_NEW, "bw11_web_cardlist_en.pdf",  "INFERRED"),

    # ─── XY Era (2014–2016) ──────────────────────────────────────────────────
    # API series: "XY"
    "xy1":   (BASE_NEW, "xy1_web_cardlist_en.pdf",   "INFERRED"),
    "xy2":   (BASE_NEW, "xy2_web_cardlist_en.pdf",   "INFERRED"),
    "xy3":   (BASE_NEW, "xy3_web_cardlist_en.pdf",   "INFERRED"),
    "xy4":   (BASE_NEW, "xy4_web_cardlist_en.pdf",   "INFERRED"),
    "xy5":   (BASE_NEW, "xy5_web_cardlist_en.pdf",   "INFERRED"),
    "xy6":   (BASE_NEW, "xy6_web_cardlist_en.pdf",   "INFERRED"),
    "xy7":   (BASE_NEW, "xy7_web_cardlist_en.pdf",   "INFERRED"),
    "xy8":   (BASE_NEW, "xy8_web_cardlist_en.pdf",   "INFERRED"),
    "xy9":   (BASE_NEW, "xy9_web_cardlist_en.pdf",   "INFERRED"),
    "xy10":  (BASE_NEW, "xy10_web_cardlist_en.pdf",  "INFERRED"),
    "xy11":  (BASE_NEW, "xy11_web_cardlist_en.pdf",  "INFERRED"),
    "xy12":  (BASE_NEW, "xy12_web_cardlist_en.pdf",  "INFERRED"),

    # ─── Sun & Moon Era (2017–2019) ──────────────────────────────────────────
    # API series: "Sun & Moon"
    "sm1":   (BASE_NEW, "sm1_web_cardlist_en.pdf",   "INFERRED"),
    "sm2":   (BASE_NEW, "sm2_web_cardlist_en.pdf",   "INFERRED"),
    "sm3":   (BASE_NEW, "sm3_web_cardlist_en.pdf",   "INFERRED"),
    "sm4":   (BASE_NEW, "sm4_web_cardlist_en.pdf",   "INFERRED"),
    "sm5":   (BASE_NEW, "sm5_web_cardlist_en.pdf",   "INFERRED"),
    "sm6":   (BASE_NEW, "sm6_web_cardlist_en.pdf",   "INFERRED"),
    "sm7":   (BASE_NEW, "sm7_web_cardlist_en.pdf",   "INFERRED"),
    "sm75":  (BASE_NEW, "sm75_web_cardlist_en.pdf",  "INFERRED"),  # Dragon Majesty
    "sm8":   (BASE_NEW, "sm8_web_cardlist_en.pdf",   "INFERRED"),
    "sm9":   (BASE_NEW, "sm9_web_cardlist_en.pdf",   "INFERRED"),
    "sm10":  (BASE_NEW, "sm10_web_cardlist_en.pdf",  "INFERRED"),
    "sm11":  (BASE_NEW, "sm11_web_cardlist_en.pdf",  "INFERRED"),
    "sm115": (BASE_NEW, "sm115_web_cardlist_en.pdf", "INFERRED"),  # Hidden Fates
    "sm12":  (BASE_NEW, "sm12_web_cardlist_en.pdf",  "INFERRED"),

    # ─── Sword & Shield Era (2020–2023) ──────────────────────────────────────
    # API series: "Sword & Shield"
    "swsh1":   (BASE_NEW, "swsh1_web_cardlist_en.pdf",   "INFERRED"),
    "swsh2":   (BASE_NEW, "swsh2_web_cardlist_en.pdf",   "INFERRED"),
    "swsh3":   (BASE_NEW, "swsh3_web_cardlist_en.pdf",   "INFERRED"),
    "swsh35":  (BASE_NEW, "swsh35_web_cardlist_en.pdf",  "INFERRED"),  # Champion's Path
    "swsh4":   (BASE_NEW, "swsh4_web_cardlist_en.pdf",   "INFERRED"),
    "swsh45":  (BASE_NEW, "swsh45_web_cardlist_en.pdf",  "INFERRED"),  # Shining Fates
    "swsh5":   (BASE_NEW, "swsh5_web_cardlist_en.pdf",   "INFERRED"),
    "swsh6":   (BASE_NEW, "swsh6_web_cardlist_en.pdf",   "INFERRED"),
    "swsh7":   (BASE_NEW, "swsh7_web_cardlist_en.pdf",   "CONFIRMED"),
    "cel25":   (BASE_NEW, "25th_web_cardlist_en.pdf",    "CONFIRMED"),  # Celebrations
    "swsh8":   (BASE_NEW, "swsh8_web_cardlist_en.pdf",   "CONFIRMED"),
    "swsh9":   (BASE_NEW, "swsh9_web_cardlist_en.pdf",   "CONFIRMED"),
    "swsh10":  (BASE_NEW, "swsh10_web_cardlist_en.pdf",  "INFERRED"),
    "swsh105": (BASE_NEW, "swsh105_web_cardlist_en.pdf", "INFERRED"),  # Pokémon GO
    "swsh11":  (BASE_NEW, "swsh11_web_cardlist_en.pdf",  "CONFIRMED"),
    "swsh12":  (BASE_NEW, "swsh12_web_cardlist_en.pdf",  "INFERRED"),
    "swsh125": (BASE_NEW, "swsh125_web_cardlist_en.pdf", "INFERRED"),  # Crown Zenith

    # ─── Scarlet & Violet Era (2023–) ────────────────────────────────────────
    # API series: "Scarlet & Violet"
    "sv1":   (BASE_NEW, "sv1_web_cardlist_en.pdf",   "INFERRED"),
    "sv2":   (BASE_NEW, "pal_web_cardlist_en.pdf",   "CONFIRMED"),   # Paldea Evolved
    "sv3":   (BASE_NEW, "obf_web_cardlist_en.pdf",   "CONFIRMED"),   # Obsidian Flames
    "sv3pt5":(BASE_NEW, "sv35_web_cardlist_en.pdf",  "INFERRED"),    # 151
    "sv4":   (BASE_NEW, "par_web_cardlist_en.pdf",   "INFERRED"),    # Paradox Rift
    "sv4pt5":(BASE_NEW, "paf_web_cardlist_en.pdf",   "INFERRED"),    # Paldean Fates
    "sv5":   ("https://tcg.pokemon.com/assets/img/sv-expansions/temporal-forces/download/en-us/",
              "SV05-Card-List-EN.pdf", "CONFIRMED"),                  # Temporal Forces
    "sv6":   (BASE_NEW, "twm_web_cardlist_en.pdf",   "CONFIRMED"),   # Twilight Masquerade
    "sv6pt5":(BASE_NEW, "shr_web_cardlist_en.pdf",   "INFERRED"),    # Shrouded Fable
    "sv7":   (BASE_NEW, "stc_web_cardlist_en.pdf",   "INFERRED"),    # Stellar Crown
    "sv8":   (BASE_NEW, "ssp_web_cardlist_en.pdf",   "CONFIRMED"),   # Surging Sparks
    "sv8pt5":(BASE_NEW, "pre_web_cardlist_en.pdf",   "CONFIRMED"),   # Prismatic Evolutions
    "sv9":   (BASE_NEW, "dri_web_cardlist_en.pdf",   "INFERRED"),    # Destined Rivals
    "sv9pt5":(BASE_NEW, "jtg_web_cardlist_en.pdf",   "CONFIRMED"),   # Journey Together
    "sv10":  (BASE_NEW, "blk_web_cardlist_en.pdf",   "CONFIRMED"),   # Black Bolt
}


def get_checklist_url(set_code: str) -> tuple[str, str] | None:
    """
    Returns (url, confidence) for a given API set code, or None if not mapped.
    """
    entry = CHECKLIST_MAP.get(set_code.lower())
    if not entry:
        return None
    base, filename, confidence = entry
    return base + filename, confidence


if __name__ == "__main__":
    print(f"{'Set Code':12s} | {'Confidence':10s} | URL")
    print("-" * 100)
    confirmed = inferred = 0
    for code, (base, filename, conf) in CHECKLIST_MAP.items():
        url = base + filename
        print(f"{code:12s} | {conf:10s} | {url}")
        if conf == "CONFIRMED":
            confirmed += 1
        else:
            inferred += 1
    print(f"\nTotal: {confirmed + inferred} sets | CONFIRMED: {confirmed} | INFERRED: {inferred}")
