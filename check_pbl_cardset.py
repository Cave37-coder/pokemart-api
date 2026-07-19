"""
check_pbl_cardset.py
Read-only. Checks PBL's CardSet record for the release_date issue
flagged earlier this session ("PBL CardSet existed at id=174 with
incorrect release date") -- if the daily sync has any date-based guard
(e.g. skip syncing sets not yet released), a wrong release_date would
explain why PBL prices have never updated since initial creation.

Usage:
    python manage.py shell -c "exec(open('check_pbl_cardset.py').read())"
"""

from products.models import CardSet
import datetime

cs = CardSet.objects.filter(code='PBL').first()
if not cs:
    print("No CardSet found for PBL at all -- that would be a bigger problem.")
else:
    print(f"CardSet id: {cs.id}")
    print(f"code: {cs.code}")
    print(f"name: {cs.name}")
    print(f"era: {cs.era.code if cs.era else None}")
    print(f"release_date: {cs.release_date!r}")
    print(f"total_cards: {cs.total_cards}")
    print(f"regulation_mark: {cs.regulation_mark!r}")
    print()
    today = datetime.date.today()
    print(f"Today's date: {today}")
    if cs.release_date:
        if cs.release_date > today:
            print(f"release_date IS in the future ({cs.release_date}) -- if the sync has a")
            print("'don't sync unreleased sets' guard, THIS would explain the total freeze.")
        else:
            print(f"release_date is NOT in the future ({cs.release_date} <= {today}) --")
            print("a date-guard theory doesn't hold unless the guard uses different logic.")
    else:
        print("release_date is NULL/blank -- if the sync guard checks 'release_date is set")
        print("AND in the past', a null value would also cause it to be skipped.")
