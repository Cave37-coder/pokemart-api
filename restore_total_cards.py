"""
restore_total_cards.py -- PokeBulk SA

fix_total_cards.py (run 2026-11-03 after the Delta Reign sync) overwrote CardSet.total_cards with the number
of product ROWS (every variant counted) for 135 sets. The checklist card numbers (e.g. "001/154") and every
saved tick are keyed on that total, so My Sets progress "reset" and the 30C Pikachu sub-set broke.

These are the totals the sets had before, rebuilt from the checklistData.ts that was live before the
regeneration (git 04491c9): for each set, the printed total most of its card numbers carried.

  python manage.py shell -c "exec(open('restore_total_cards.py').read())"                 # dry run
  python manage.py shell -c "import os; os.environ['RESTORE_APPLY']='1'; exec(open('restore_total_cards.py').read())"

NOT restored here (no safe old value could be derived -- left as they are, see the notes in chat):
SVP, PRIZEPACK, SVE, MEE.   DLR is set to its printed total, 103.
"""
import os
from products.models import CardSet

APPLY = os.environ.get("RESTORE_APPLY") == "1"

OLD_TOTALS = {
 "GEN": 83, "PLF": 116, "DRV": 20, "PHF": 119, "PLS": 135, "AOR": 98, "POR": 88, "PR-BLW": 102, "RCL": 192,
 "ASC": 217, "BCR": 149, "PR-HS": 26, "30C": 154, "MA": 95, "PAR": 182, "PRE": 131, "TM": 102, "CRE": 198,
 "NXD": 99, "CRI": 86, "LTR": 113, "FST": 264, "DRM": 70, "MD": 100, "N4": 105, "OBF": 197, "SW": 132,
 "FCO": 124, "DCR": 34, "DP": 130, "BST": 163, "PR-NB": 62, "GE": 106, "SFA": 64, "BRS": 172, "PR-DP": 58,
 "FFI": 111, "MEW": 165, "DX": 107, "RR": 111, "BKT": 162, "PLB": 101, "UL": 95, "PRC": 160, "RS": 109,
 "WHT": 86, "SM05": 156, "XY": 146, "SVI": 198, "LM": 92, "DR": 97, "AQ": 147, "EVS": 203, "UF": 115,
 "SHL": 73, "SM9": 181, "LOR": 196, "TR": 82, "MEP": 86, "SM02": 145, "CHP": 73, "HS": 123, "TEF": 162,
 "DS": 113, "CRZ": 159, "PK": 108, "SM06": 131, "SIT": 195, "DRX": 124, "ROS": 108, "PR-XY": 217, "EPO": 98,
 "EVO": 108, "N3": 64, "PBL": 204, "LA": 146, "BKP": 122, "PFL": 94, "KSS": 39, "STS": 114, "SM10": 214,
 "SM03": 147, "HP": 110, "PR-BEST": 9, "AR": 99, "SM11": 236, "CES": 168, "MEG": 132, "DEX": 108, "DRI": 182,
 "SSP": 191, "PGO": 78, "PR-SWSH": 311, "HIF": 68, "PR-WB": 60, "VIV": 185, "EX": 165, "BLW": 114, "CLB": 25,
 "CoL": 95, "SM04": 111, "TWM": 167, "MT": 123, "SF": 100, "JTG": 159, "CG": 100, "PAL": 193, "DAA": 189,
 "LC": 110, "SM12": 236, "SM01": 149, "FLF": 106, "RG": 112, "SSH": 202, "BLK": 86, "TRR": 109, "SCR": 142,
 "SM8": 214, "PL": 127, "SS": 100, "SHF": 72, "DF": 101, "DET": 17, "SK": 144, "NVI": 101, "PAF": 91,
 "EM": 106, "HL": 101, "ASR": 189, "UD": 90,
 "DLR": 103,   # Delta Reign printed total (cards 104-141 are the numbered-past-the-set secrets)
}

print(f"Mode: {'APPLY' if APPLY else 'DRY RUN'}\n")
changed = 0
for code, total in sorted(OLD_TOTALS.items()):
    cs = CardSet.objects.filter(code=code).first()
    if not cs:
        print(f"  {code}: no such CardSet, skipped")
        continue
    if cs.total_cards == total:
        continue
    print(f"  {code}: {cs.total_cards} -> {total}")
    if APPLY:
        cs.total_cards = total
        cs.save(update_fields=["total_cards"])
    changed += 1
print(f"\n{changed} set(s) {'restored' if APPLY else 'would be restored'}.")
if not APPLY:
    print("Dry run only. Re-run with RESTORE_APPLY=1 to write.")
