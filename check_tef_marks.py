import requests

r = requests.get('https://api.pokemontcg.io/v2/cards', params={'q': 'set.id:sv5', 'pageSize': 250})
data = r.json()['data']

marks = {}
for c in data:
    m = c.get('regulationMark', 'NONE')
    marks.setdefault(m, []).append(f"{c['number']} {c['name']} ({c['supertype']})")

for mark, cards in marks.items():
    print(f"=== Mark: {mark} ({len(cards)} cards) ===")
    for c in cards[:5]:
        print(" ", c)
    if len(cards) > 5:
        print(f"  ... and {len(cards) - 5} more")
