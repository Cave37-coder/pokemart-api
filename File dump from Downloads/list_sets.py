import requests
headers = {"X-Api-Key": "0ec1fcef-24b9-4239-b265-817f2c726099"}
r = requests.get("https://api.pokemontcg.io/v2/sets?pageSize=250", headers=headers)
sets = r.json()["data"]
print(f"Total sets on pokemontcg.io: {len(sets)}")
for s in sorted(sets, key=lambda x: x["releaseDate"]):
    sid = s["id"]
    name = s["name"]
    date = s["releaseDate"]
    print(f"{sid:15s} {name:40s} {date}")
