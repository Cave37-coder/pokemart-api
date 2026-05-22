import requests
sets_to_find = ["swsh9tg", "swsh10tg", "swsh11tg", "swsh12tg", "swsh12pt5gg"]
r = requests.get("https://api.pokemontcg.io/v2/sets", headers={"X-Api-Key": ""})
all_sets = r.json()["data"]
for s in all_sets:
    if s["id"] in sets_to_find or any(x in s["id"] for x in ["tg", "gg"]):
        print(f"{s['id']:20} {s['name']:40} {s['total']} cards")
