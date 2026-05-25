"""
Check if pb_id conflicts are causing silent failures
Run: python manage.py shell --command="exec(open('check_pbid_conflict.py').read())"
"""
from products.models import PokemonProduct

# Check what pb_ids would be generated for ASRTG
# TG cards have numbers TG01-TG30, parsed as 1-30
# So pb_id = ASRTG-1-H, ASRTG-2-H etc.
# Check if any of these already exist under different codes

test_pids = [f"ASRTG-{i}-H" for i in range(1, 31)]
existing = PokemonProduct.objects.filter(pb_id__in=test_pids).values('pb_id', 'card_set__code')
print(f"ASRTG pb_id conflicts: {existing.count()}")
for e in existing[:5]:
    print(f"  {e['pb_id']} -> set={e['card_set__code']}")

# Check TOT22
test_pids2 = [f"TOT22-{i}-N" for i in range(1, 31)]
existing2 = PokemonProduct.objects.filter(pb_id__in=test_pids2).values('pb_id', 'card_set__code')
print(f"\nTOT22 pb_id conflicts: {existing2.count()}")
for e in existing2[:5]:
    print(f"  {e['pb_id']} -> set={e['card_set__code']}")

# Check RUM
test_pids3 = [f"RUM-{i}-N" for i in range(1, 17)]
existing3 = PokemonProduct.objects.filter(pb_id__in=test_pids3).values('pb_id', 'card_set__code')
print(f"\nRUM pb_id conflicts: {existing3.count()}")
for e in existing3[:5]:
    print(f"  {e['pb_id']} -> set={e['card_set__code']}")

# Check MEE
test_pids4 = [f"MEE-{i}-N" for i in range(1, 17)]
existing4 = PokemonProduct.objects.filter(pb_id__in=test_pids4).values('pb_id', 'card_set__code')
print(f"\nMEE pb_id conflicts: {existing4.count()}")
for e in existing4[:5]:
    print(f"  {e['pb_id']} -> set={e['card_set__code']}")

# Check DEP
test_pids5 = [f"DEP-{i}-N" for i in range(1, 19)]
existing5 = PokemonProduct.objects.filter(pb_id__in=test_pids5).values('pb_id', 'card_set__code')
print(f"\nDEP pb_id conflicts: {existing5.count()}")
for e in existing5[:5]:
    print(f"  {e['pb_id']} -> set={e['card_set__code']}")
