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
    ("base1","BS"),("jungle","JU"),("fossil","FO"),("base4","B2"),("base5","TR"),
    ("gym1","G1"),("gym2","G2"),("neo1","N1"),("neo2","N2"),("neo3","N3"),
    ("neo4","N4"),("base6","LC"),("ex1","RS"),("ex2","SS"),("ex3","DR"),
    ("ex5","MA"),("ex6","HL"),("ex7","RG"),("ex8","TRR"),("ex11","DX"),
    ("ex13","EM"),("ex15","UF"),("ex14","DS"),("ex16","LM"),("ex17","HP"),
    ("ex12","CG"),("ex18","DF"),("ex19","PK"),("hgss1","HS"),("hgss2","UL"),
    ("hgss3","UD"),("hgss4","TM"),("col1","CL"),("bw1","BLW"),("bw2","EPO"),
    ("bw3","NVI"),("bw4","NXD"),("bw5","DEX"),("bw6","DRX"),("dv1","DRV"),
    ("bw7","BCR"),("bw8","PLS"),("bw9","PLF"),("bw10","PLB"),("bw11","LTR"),
    ("xy1","XY"),("xy2","FLF"),("xy3","FFI"),("xy4","PHF"),("xy5","PRC"),
    ("dc1","DCR"),("xy6","ROS"),("xy7","AOR"),("xy8","BKT"),("xy9","BKP"),
    ("g1","GEN"),("xy10","FCO"),("xy11","STS"),("xy12","EVO"),("sm1","SUM"),
    ("sm2","GRI"),("sm3","BUS"),("sm35","SLG"),("sm4","CIN"),("sm5","UPR"),
    ("sm6","FLI"),("sm7","CES"),("sm75","DRM"),("sm8","LOT"),("svp","SVP"),
    ("sv1","SV1"),("sv6","TWM"),("sv6pt5","SFA"),("sv7","SCR"),("sv8","SSP"),
    ("sv8pt5","PRE"),("me1","MEG"),("me2","PFL"),("me2pt5","ASC"),("me3","POR"),
]

print(f"Enriching {len(SETS)} sets on Railway...")
print("=" * 60)
print("Running migrations...")
call_command("migrate", verbosity=1)
print("Migrations done.")
print("=" * 60)

failed = []
for i, (set_id, code) in enumerate(SETS, 1):
    print(f"\n[{i}/{len(SETS)}] {code} ({set_id})")
    try:
        call_command("enrich_set", set_id, verbosity=1)
    except Exception as e:
        print(f"  FAILED: {e}")
        failed.append((set_id, code, str(e)))
    time.sleep(2)

print("\n" + "=" * 60)
print(f"Done. {len(SETS) - len(failed)} succeeded, {len(failed)} failed.")
if failed:
    print("Failed sets:")
    for s, c, e in failed:
        print(f"  {c} ({s}): {e}")
