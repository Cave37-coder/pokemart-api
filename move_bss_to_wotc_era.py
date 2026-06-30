from products.models import CardSet, Era

DRY_RUN = True  # review the printed plan, then set False and rerun

try:
    bss = CardSet.objects.get(code='BSS')
except CardSet.DoesNotExist:
    print("!! No CardSet with code 'BSS' found — check the exact code.")
    bss = None

try:
    wotc_era = Era.objects.get(code='WotC')
except Era.DoesNotExist:
    print("!! No Era with code 'WotC' found — check the exact era code.")
    wotc_era = None

if bss and wotc_era:
    current_era = bss.era.code if bss.era else None
    print(f"Base Set Shadowless (BSS): current era = {current_era!r}")
    print(f"  -> will set era = 'WotC' (id={wotc_era.id})")

    if DRY_RUN:
        print("\nDRY RUN — nothing changed. Set DRY_RUN = False and rerun to apply.")
    else:
        bss.era = wotc_era
        bss.save(update_fields=['era'])
        print("\nUpdated.")
