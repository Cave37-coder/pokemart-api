import requests, os, sys, django
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
sys.path.insert(0, ".")
django.setup()

from products.models import CardSet
from django.db.models import Count

# Get all empty sets
empty = CardSet.objects.annotate(c=Count("products")).filter(c=0).values_list("code", "name")

# Fetch all sets from pokemontcg.io
from django.conf import settings
headers = {"X-Api-Key": settings.POKEMONTCG_API_KEY} if settings.POKEMONTCG_API_KEY else {}
r = requests.get("https://api.pokemontcg.io/v2/sets?pageSize=250", headers=headers)
api_sets = {s["name"].lower(): s["id"] for s in r.json()["data"]}
api_by_id = {s["id"]: s["name"] for s in r.json()["data"]}

print("Empty DB sets and their pokemontcg.io IDs:")
found = []
for code, name in empty:
    # Try to find match
    match = None
    for aname, aid in api_sets.items():
        if name.lower() in aname or aname in name.lower():
            match = aid
            break
    if match:
        found.append(match)
        print(f"  [{code}] {name} -> {match}")
    else:
        print(f"  [{code}] {name} -> NOT FOUND")

print(f"\nRun: python enrich_all2.py")
with open("enrich_all2.py", "w") as f:
    f.write("import subprocess, sys\nSETS = " + str(found) + "\n")
    f.write("for s in SETS:\n    print(f'Enriching {s}...')\n    subprocess.run([sys.executable, 'manage.py', 'enrich_set', s])\n")
