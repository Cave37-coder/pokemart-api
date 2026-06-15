import os, sys, django, time

RAILWAY_DB_NAME     = "railway"
RAILWAY_DB_USER     = "postgres"
RAILWAY_DB_PASSWORD = "dUVDSrYQsZUkkubLuioIPTqUqqTlRBXm"
RAILWAY_DB_HOST     = "nozomi.proxy.rlwy.net"
RAILWAY_DB_PORT     = "59678"

os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
os.environ["DB_NAME"]     = RAILWAY_DB_NAME
os.environ["DB_USER"]     = RAILWAY_DB_USER
os.environ["DB_PASSWORD"] = RAILWAY_DB_PASSWORD
os.environ["DB_HOST"]     = RAILWAY_DB_HOST
os.environ["DB_PORT"]     = RAILWAY_DB_PORT

sys.path.insert(0, os.getcwd())
django.setup()

from django.core.management import call_command

SETS = [
    "basep","si1","ecard1","ecard2","ecard3","bp",
    "ex4","ex5","ex6","ex7","ex8","ex9","ex10","ex11","ex12","ex13","ex14","ex15","ex16",
    "pop1","pop2","pop3","pop4","pop5","pop6","pop7","pop8","pop9",
    "dp1","dpp","dp2","dp3","dp4","dp5","dp6","dp7","pl1","pl2","pl3","pl4",
    "bwp","mcd11","mcd12","smp","mcd14","mcd15","mcd16",
    "sm9","det1","sm10","sm11","sm115","sma","mcd17","mcd18","mcd19","sm12",
    "swshp","swsh1","swsh2","swsh3","swsh35","swsh4","swsh45","swsh5",
    "swsh6","swsh7","cel25","swsh8","swsh9","swsh10","pgo","swsh11",
    "swsh12","swsh12pt5","mcd21","mcd22",
    "sv2","sv3","sv3pt5","sv4","sv4pt5","sv5","sv9","sv10","zsv10pt5","rsv10pt5",
]

print(f"Enriching {len(SETS)} sets on Railway...")
print("=" * 60)
failed = []
for i, set_id in enumerate(SETS, 1):
    print(f"\n[{i}/{len(SETS)}] {set_id}")
    try:
        call_command("enrich_set", set_id, verbosity=1)
    except Exception as e:
        print(f"  FAILED: {e}")
        failed.append((set_id, str(e)))
    time.sleep(2)

print("\n" + "=" * 60)
print(f"Done. {len(SETS)-len(failed)} succeeded, {len(failed)} failed.")
if failed:
    for s, e in failed: print(f"  {s}: {e}")
