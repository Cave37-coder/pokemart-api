"""
verify_checklists.py
Run from anywhere: python verify_checklists.py

HEAD-checks all 102 pokemon.com checklist URLs.
Prints a clean report and writes results to checklist_verification.json.
"""

import json
import time
import urllib.request
import urllib.error
from checklist_url_map import CHECKLIST_MAP

TIMEOUT = 10
DELAY   = 0.25   # polite delay between requests

results = {}
ok = []
broken = []

print(f"Checking {len(CHECKLIST_MAP)} URLs...\n")
print(f"{'Code':12s} {'Status':8s} {'Confidence':10s}  URL")
print("─" * 110)

for code, (base, filename, confidence) in CHECKLIST_MAP.items():
    url = base + filename
    try:
        req = urllib.request.Request(url, method="HEAD")
        req.add_header("User-Agent", "Mozilla/5.0 (compatible; PokeBulkSA/1.0)")
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            status = resp.status
    except urllib.error.HTTPError as e:
        status = e.code
    except urllib.error.URLError as e:
        status = f"ERR: {e.reason}"
    except Exception as e:
        status = f"ERR: {e}"

    is_ok = status == 200
    marker = "✓" if is_ok else "✗"
    print(f"{marker} {code:10s} {str(status):8s} {confidence:10s}  {filename}")

    results[code] = {"url": url, "status": status, "confidence": confidence, "ok": is_ok}
    if is_ok:
        ok.append(code)
    else:
        broken.append((code, status, url))

    time.sleep(DELAY)

print("\n" + "═" * 110)
print(f"\n✓  LIVE:   {len(ok)} sets")
print(f"✗  BROKEN: {len(broken)} sets")

if broken:
    print("\nBROKEN URLs:")
    for code, status, url in broken:
        print(f"  {code:12s}  [{status}]  {url}")

with open("checklist_verification.json", "w") as f:
    json.dump(results, f, indent=2)

print("\nFull results saved to checklist_verification.json")
