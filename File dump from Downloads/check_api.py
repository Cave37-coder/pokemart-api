import urllib.request, json
url = 'https://pokemart-api-production.up.railway.app/api/sets/?limit=200'
with urllib.request.urlopen(url) as r:
    data = json.load(r)
print('Total sets returned:', len(data.get('results', [])))
for s in data.get('results', []):
    print(s.get('era_code','?'), '|', s.get('code','?'), '|', s.get('name','?'))
