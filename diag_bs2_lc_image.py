import requests

# BS2 and LC came back 0/130 and 0/110 verified even in an isolated, slow,
# Referer-header retry -- ruling out rate-limiting. Page fetch + name match
# succeed fine (confirmed manually: legendary/003.shtml really is Charizard),
# but the .jpg fetch itself fails for every single card in both sets. This
# prints the RAW response (status code, headers, body length/snippet) for a
# couple of known-good image URLs so we can see exactly what Serebii is
# sending back instead of just "failed".

UA = "PokeBulkSA/1.0.0 (enquiries@pokebulk.co.za)"
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

URLS = [
    "https://www.serebii.net/card/baseset2/4.jpg",
    "https://www.serebii.net/card/baseset2/004.jpg",
    "https://www.serebii.net/card/legendary/3.jpg",
    "https://www.serebii.net/card/legendary/003.jpg",
]

for label, ua, referer in [
    ("PokeBulkSA UA, no referer", UA, None),
    ("PokeBulkSA UA, with referer", UA, "https://www.serebii.net/card/baseset2/004.shtml"),
    ("Browser UA, no referer", BROWSER_UA, None),
    ("Browser UA, with referer", BROWSER_UA, "https://www.serebii.net/card/baseset2/004.shtml"),
]:
    print(f"\n=== {label} ===")
    headers = {"User-Agent": ua}
    if referer:
        headers["Referer"] = referer
    for url in URLS[:2]:  # just the baseset2 ones to keep it short
        try:
            r = requests.get(url, headers=headers, timeout=20)
            body_snippet = r.content[:200]
            print(f"  {url}")
            print(f"    status={r.status_code} content-type={r.headers.get('Content-Type')} "
                  f"content-length={r.headers.get('Content-Length')} actual_bytes={len(r.content)}")
            print(f"    response headers: {dict(r.headers)}")
            if r.status_code != 200 or (r.headers.get('Content-Type') and 'image' not in r.headers.get('Content-Type')):
                print(f"    body snippet: {body_snippet}")
        except Exception as e:
            print(f"  {url} -> EXCEPTION: {e}")
