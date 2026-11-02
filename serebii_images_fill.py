"""
serebii_images_fill.py -- PokeBulk SA
Fills blank bulba_image_url in an enriched bible-format CSV with the card's OWN Serebii image
(https://www.serebii.net/card/<slug>/<n>.jpg). Use it after enrich_bulbapedia.py and BEFORE
download_images_to_r2_v1.0.py, which then copies the image to R2 (rule: never hotlink).

Only touches card rows whose bulba_image_url is blank. Never overwrites a Bulbapedia image.
Each URL is checked (HTTP 200 + image content-type); the page HTML is used as a fallback to find the image.
Writes a NEW csv (<in>_serebii.csv) and a report of anything it could not find.

  python serebii_images_fill.py --in check_sheets\DLR_bible_format_check_expanded_bulba_enriched.csv --slug deltareign --set DLR
"""
import argparse
import csv
import re
import sys
import time

import requests

UA = "PokeBulkSA/1.0.0 (enquiries@pokebulk.co.za)"


def is_image(url):
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=20, stream=True)
        ok = r.status_code == 200 and r.headers.get("content-type", "").lower().startswith("image")
        r.close()
        return ok
    except Exception:
        return False


def find_image(slug, n):
    base = f"https://www.serebii.net/card/{slug}"
    for u in (f"{base}/{n}.jpg", f"{base}/{n:03d}.jpg", f"{base}/{n}.png"):
        if is_image(u):
            return u
    try:  # fallback: read the page and look for the card image
        r = requests.get(f"{base}/{n:03d}.shtml", headers={"User-Agent": UA}, timeout=20)
        if r.status_code == 200:
            for m in re.finditer(r'src="([^"]*/card/%s/[^"]+\.(?:jpg|png))"' % re.escape(slug), r.text):
                u = m.group(1)
                u = u if u.startswith("http") else "https://www.serebii.net" + u
                if re.search(r'/0*%d\.(?:jpg|png)$' % n, u) and is_image(u):
                    return u
    except Exception:
        pass
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--set", required=True)
    ap.add_argument("--delay", type=float, default=0.5)
    a = ap.parse_args()

    with open(a.inp, encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f)
        cols, rows = rd.fieldnames, list(rd)
    if "serebii_image_url" not in cols:
        cols.append("serebii_image_url")

    cache, filled, missing = {}, 0, []
    for r in rows:
        r.setdefault("serebii_image_url", "")
        if str(r.get("is_card", "")).lower() not in ("true", "1") or r.get("set_code") != a.set:
            continue
        if (r.get("bulba_image_url") or "").strip():
            continue
        m = re.match(r"\d+", str(r.get("number") or r.get("card_number") or "").strip())
        if not m:
            continue
        n = int(m.group(0))
        if n not in cache:
            cache[n] = find_image(a.slug, n)
            time.sleep(a.delay)
        if cache[n]:
            r["serebii_image_url"] = cache[n]
            r["bulba_image_url"] = cache[n]
            r["final_image_source"] = "serebii"
            filled += 1
        else:
            missing.append((r.get("name"), n))

    out = re.sub(r"\.csv$", "", a.inp) + "_serebii.csv"
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"Filled {filled} row(s) from Serebii -> {out}")
    print(f"No Serebii image found for {len(missing)} row(s) (will fall back to TCGplayer):")
    for nm, n in sorted(set(missing), key=lambda x: x[1]):
        print(f"   #{n:03d} {nm}")


if __name__ == "__main__":
    sys.exit(main())
