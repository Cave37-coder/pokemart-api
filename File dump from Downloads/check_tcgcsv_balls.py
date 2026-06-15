import requests

# Try correct TCGCSV endpoint
urls = [
    "https://tcgcsv.com/groups",
    "https://tcgcsv.com/tcgplayer/groups",
    "https://tcgcsv.com/tcgplayer/1/groups",
    "https://tcgcsv.com/tcgplayer/2/groups",
]
for url in urls:
    try:
        r = requests.get(url, timeout=5)
        print(f"{url} -> {r.status_code} {len(r.text)} bytes")
        if r.status_code == 200 and len(r.text) > 10:
            data = r.json()
            print(f"  Keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
            break
    except Exception as e:
        print(f"{url} -> ERROR: {e}")
