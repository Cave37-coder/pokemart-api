import os, sys, django, time

os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
sys.path.insert(0, os.getcwd())
django.setup()

from django.core.management import call_command

# All missing sets grouped by era
MISSING = [
    # WotC era (B1) - missing
    ("basep",   "Wizards Black Star Promos"),
    ("si1",     "Southern Islands"),
    ("ecard1",  "Expedition Base Set"),
    ("ecard2",  "Aquapolis"),
    ("ecard3",  "Skyridge"),
    ("bp",      "Best of Game"),

    # EX era (B2) - wrong IDs in your DB
    ("ex4",     "Team Magma vs Team Aqua"),  # you have ex5
    ("ex5",     "Hidden Legends"),           # you have ex6
    ("ex6",     "FireRed & LeafGreen"),      # you have ex7
    ("ex7",     "Team Rocket Returns"),      # you have ex8
    ("ex8",     "Deoxys"),                   # you have ex11
    ("ex9",     "Emerald"),                  # you have ex13
    ("ex10",    "Unseen Forces"),            # you have ex15
    ("ex11",    "Delta Species"),            # you have ex14
    ("ex12",    "Legend Maker"),             # you have ex16
    ("ex13",    "Holon Phantoms"),           # you have ex17
    ("ex14",    "Crystal Guardians"),        # you have ex12
    ("ex15",    "Dragon Frontiers"),         # you have ex18
    ("ex16",    "Power Keepers"),            # you have ex19

    # POP Series (new era)
    ("pop1",    "POP Series 1"),
    ("pop2",    "POP Series 2"),
    ("pop3",    "POP Series 3"),
    ("pop4",    "POP Series 4"),
    ("pop5",    "POP Series 5"),
    ("pop6",    "POP Series 6"),
    ("pop7",    "POP Series 7"),
    ("pop8",    "POP Series 8"),
    ("pop9",    "POP Series 9"),

    # Diamond & Pearl era (B3) - missing
    ("dp1",     "Diamond & Pearl"),
    ("dpp",     "DP Black Star Promos"),
    ("dp2",     "Mysterious Treasures"),
    ("dp3",     "Secret Wonders"),
    ("dp4",     "Great Encounters"),
    ("dp5",     "Majestic Dawn"),
    ("dp6",     "Legends Awakened"),
    ("dp7",     "Stormfront"),
    ("pl1",     "Platinum"),
    ("pl2",     "Rising Rivals"),
    ("pl3",     "Supreme Victors"),
    ("pl4",     "Arceus"),

    # BW era (B4) - missing promos + McD
    ("bwp",     "BW Black Star Promos"),
    ("mcd11",   "McDonalds 2011"),
    ("mcd12",   "McDonalds 2012"),

    # XY era (B5) - missing
    ("smp",     "SM Black Star Promos"),
    ("mcd14",   "McDonalds 2014"),
    ("mcd15",   "McDonalds 2015"),
    ("mcd16",   "McDonalds 2016"),

    # SM era (B6) - missing
    ("sm9",     "Team Up"),
    ("det1",    "Detective Pikachu"),
    ("sm10",    "Unbroken Bonds"),
    ("sm11",    "Unified Minds"),
    ("sm115",   "Hidden Fates"),
    ("sma",     "Hidden Fates Shiny Vault"),
    ("mcd17",   "McDonalds 2017"),
    ("mcd18",   "McDonalds 2018"),
    ("mcd19",   "McDonalds 2019"),
    ("sm12",    "Cosmic Eclipse"),

    # Sword & Shield era (B7) - ALL missing
    ("swshp",   "SWSH Black Star Promos"),
    ("swsh1",   "Sword & Shield"),
    ("swsh2",   "Rebel Clash"),
    ("swsh3",   "Darkness Ablaze"),
    ("swsh35",  "Champions Path"),
    ("swsh4",   "Vivid Voltage"),
    ("swsh45",  "Shining Fates"),
    ("swsh5",   "Battle Styles"),
    ("swsh6",   "Chilling Reign"),
    ("swsh7",   "Evolving Skies"),
    ("cel25",   "Celebrations"),
    ("swsh8",   "Fusion Strike"),
    ("swsh9",   "Brilliant Stars"),
    ("swsh10",  "Astral Radiance"),
    ("pgo",     "Pokemon GO"),
    ("swsh11",  "Lost Origin"),
    ("swsh12",  "Silver Tempest"),
    ("swsh12pt5","Crown Zenith"),
    ("mcd21",   "McDonalds 2021"),
    ("mcd22",   "McDonalds 2022"),

    # SV era (B8) - missing
    ("sv2",     "Paldea Evolved"),
    ("sv3",     "Obsidian Flames"),
    ("sv3pt5",  "151"),
    ("sv4",     "Paradox Rift"),
    ("sv4pt5",  "Paldean Fates"),
    ("sv5",     "Temporal Forces"),
    ("sv9",     "Journey Together"),
    ("sv10",    "Destined Rivals"),
    ("zsv10pt5","Black Bolt"),
    ("rsv10pt5","White Flare"),
]

print(f"Missing sets to enrich: {len(MISSING)}")
for sid, name in MISSING:
    print(f"  {sid:15s} {name}")
