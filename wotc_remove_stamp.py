"""
WotC "remove the 1st Edition stamp" images (2026-11-06) -- Michael: "script
please".

Every public scan of a WotC card is the 1st EDITION print. The Shadowless
(Base Set 1st Ed & Shadowless, N/H rows) and the Unlimited rows of Jungle,
Fossil, Team Rocket, Gym Heroes/Challenge and Neo 1-4 are the SAME card
without the stamp. So for each of those rows this script:
  1. takes the 1st Edition scan of the same card (the FE row's R2 image),
  2. finds the stamp by template matching (template = the stamp on the
     Base Set Charizard scan),
  3. paints the stamp's ink out (OpenCV inpaint) and keeps everything else,
  4. uploads the result to R2 and points the N/H row(s) at it.

The stamp sits in one of three places, all handled: Pokemon cards (left of
the length/weight bar), Trainers (bottom-left of the text box), Energy (top
right, in the ENERGY header). Prototype checked on Charizard, Bulbasaur,
Bill, Fire/Water Energy, Snorlax, Gengar, Dark Charizard, Misty, Shining
Charizard; unstamped Unlimited scans scored 0.47-0.52 against 0.61-1.00 for
stamped ones, so anything that doesn't clearly match is SKIPPED and listed,
never guessed.

Needs:  pip install opencv-python-headless numpy

PREVIEW (default, writes nothing to DB/R2): saves before/after crops of the
first 40 cards into .\\stamp_preview\\ -- open stamp_preview\\index.html.
    python manage.py shell -c "exec(open('wotc_remove_stamp.py').read())"
LIVE:
    $env:LIVE="1"; python manage.py shell -c "exec(open('wotc_remove_stamp.py').read())"; Remove-Item Env:LIVE
Resumable: rows already on their stamp-free image are skipped.
"""
import os
import time
import requests
import numpy as np
import cv2
import boto3
from botocore.config import Config
from django.db import connection
from products.models import PokemonProduct

LIVE = os.environ.get("LIVE") == "1"
# PASS2 (2026-11-06, Michael: "rerun") -- for the 49 cards pass 1 skipped:
# dark-framed Neo cards, Special Energies, Unown, some Trainers. Searches ONLY
# the three places a stamp is printed, and judges "ink" relative to the
# local background (a black stamp on a dark frame still stands out that way).
# Prototype: those cards scored 0.66-0.73 where the stamp really is, cards
# with no stamp scored at most 0.53.
PASS2 = os.environ.get("PASS2") == "1"
# FORCE (2026-11-06): redo rows that already have a stamp-free image. Needed
# because a spot check found pass 1 had matched the WRONG place on a few cards
# (e.g. Neo Discovery Unown [A] (14): the stamp was still there and something
# else had been painted out). Pass 2's search only looks where stamps are
# printed, so FORCE + PASS2 rebuilds every card from its 1st Edition scan.
FORCE = os.environ.get("FORCE") == "1"
PREVIEW_LIMIT = 60 if PASS2 else 40
# Exact spots (at 610x835) where the stamp sits on almost every card; a match
# right there is accepted at a lower score than elsewhere in the zones.
STANDARD_SPOTS = [(14, 42, 428, 456),    # Pokemon
                  (90, 120, 730, 760),   # Trainer
                  (495, 525, 40, 70)]    # Energy
ACCEPT_AT_SPOT = 0.45


def at_standard_spot(x, y):
    return any(x0 <= x <= x1 and y0 <= y <= y1 for x0, x1, y0, y1 in STANDARD_SPOTS)
# Scans that turned out to have NO stamp at all (TCGplayer uses a Shadowless
# scan for these) -- the scan already is the Shadowless/Unlimited image, so
# it is used as-is.
NO_STAMP_IN_SCAN = {147229}   # BSS Pikachu (Red Cheeks)
ZONES = [(0.00, 0.16, 0.46, 0.62),   # Pokemon: left of the length/weight bar
         (0.06, 0.30, 0.80, 0.95),   # Trainer: bottom-left of the text box
         (0.70, 1.00, 0.00, 0.15)]   # Energy: in the ENERGY header

R2_ACCESS_KEY_ID = "fdff88cee69c515cf67d4ae275d1bc72"
R2_SECRET_ACCESS_KEY = "e7122d20bd2ad8121756a86f4165af40be5fd3efe40fbdca5f5ca922bb1ace8f"
R2_ENDPOINT = "https://229506129ad4206787dd4d3227608e17.r2.cloudflarestorage.com"
R2_BUCKET = "pokebulkcards"
PUBLIC_URL = "https://images.pokebulk.co.za"
s3 = boto3.client("s3", endpoint_url=R2_ENDPOINT, aws_access_key_id=R2_ACCESS_KEY_ID,
                  aws_secret_access_key=R2_SECRET_ACCESS_KEY,
                  config=Config(signature_version="s3v4"), region_name="auto")
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0 Safari/537.36"}

SETS = ["BSS", "JU", "FO", "TR", "G1", "G2", "N1", "N2", "N3", "N4"]
NW, NH = 610, 835                 # every scan is normalised to this for matching
REF_URL = f"{PUBLIC_URL}/cards/BSS/wotc_exact/TCGCSV_106999_FE.jpg"   # Base Set Charizard 1st Ed
REF_BOX = (36, 444, 46, 46)       # stamp box on the reference, at 610x835
ACCEPT = 0.60                     # match score needed anywhere on the card
ACCEPT_IN_ZONE = 0.52             # ...or this, if it's where a stamp normally is


def fetch(url):
    for _ in range(3):
        try:
            r = requests.get(url, timeout=20, headers=HEADERS)
            if r.status_code == 200 and len(r.content) > 2000:
                img = cv2.imdecode(np.frombuffer(r.content, np.uint8), cv2.IMREAD_COLOR)
                if img is not None:
                    return img
        except Exception:
            pass
        time.sleep(0.5)
    return None


def ink_for_match(img_small):
    if PASS2:
        # darker than 60% of the local background brightness
        g = cv2.cvtColor(img_small, cv2.COLOR_BGR2GRAY).astype(np.float32)
        bg = cv2.blur(g, (41, 41))
        return (g < 0.6 * bg).astype(np.float32)
    # black ink: every channel dark (keeps red/blue Energy headers out)
    return (img_small.max(axis=2) < 100).astype(np.float32)


def half(img):
    return cv2.resize(img, (NW // 2, NH // 2), interpolation=cv2.INTER_AREA)


ref = fetch(REF_URL)
if ref is None:
    raise SystemExit("Could not download the reference Charizard scan from R2")
ref_ink = ink_for_match(half(cv2.resize(ref, (NW, NH), interpolation=cv2.INTER_AREA)))
rx, ry, rw, rh = [v // 2 for v in REF_BOX]
TEMPLATE = ref_ink[ry:ry + rh, rx:rx + rw]


def in_zone(x, y):
    fx, fy = x / NW, y / NH
    pokemon = fx < 0.14 and 0.48 < fy < 0.60
    trainer = 0.10 < fx < 0.26 and 0.84 < fy < 0.93
    energy = fx > 0.76 and fy < 0.12
    return pokemon or trainer or energy


def find_stamp(img):
    """-> (score, x, y, size) in 610x835 coords, best over a few scales."""
    small_ink = ink_for_match(half(cv2.resize(img, (NW, NH), interpolation=cv2.INTER_AREA)))
    best = (-1, 0, 0, 46)
    for s in (0.8, 0.9, 1.0, 1.1, 1.2):
        t = cv2.resize(TEMPLATE, (max(8, round(rw * s)), max(8, round(rh * s))), interpolation=cv2.INTER_NEAREST)
        if t.std() == 0:
            continue
        res = cv2.matchTemplate(small_ink, t, cv2.TM_CCOEFF_NORMED)
        if PASS2:
            # only where stamps are printed
            allowed = np.zeros_like(res, dtype=bool)
            rh2, rw2 = res.shape
            for ax, bx, ay, by in ZONES:
                allowed[int(ay * NH / 2):min(rh2, int(by * NH / 2)), int(ax * NW / 2):min(rw2, int(bx * NW / 2))] = True
            res = np.where(allowed, res, -1)
        _, mx, _, loc = cv2.minMaxLoc(res)
        if mx > best[0]:
            best = (mx, loc[0] * 2, loc[1] * 2, round(46 * s))
    return best


def remove_stamp(img, x, y, size):
    """Paint out only the stamp's ink inside the matched box, in the scan's own resolution."""
    H, W = img.shape[:2]
    sx, sy = W / NW, H / NH
    m = 4
    X0, Y0 = max(0, int((x - m) * sx)), max(0, int((y - m) * sy))
    X1, Y1 = min(W, int((x + size + m) * sx)), min(H, int((y + size + m) * sy))
    pad = int(30 * sx)
    wx0, wy0, wx1, wy1 = max(0, X0 - pad), max(0, Y0 - pad), min(W, X1 + pad), min(H, Y1 + pad)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    med = np.percentile(gray[Y0:Y1, X0:X1], 60)
    win = (gray[wy0:wy1, wx0:wx1] < 0.55 * med).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(win, connectivity=4)
    mask = np.zeros((H, W), np.uint8)
    kept = 0
    for i in range(1, n):
        cx, cy, cw, ch, _area = stats[i]
        ax0, ay0 = cx + wx0, cy + wy0
        # keep only blobs that sit entirely inside the stamp box: the stamp's
        # letters/circle. Card borders, the length bar etc. run outside it.
        if ax0 >= X0 and ay0 >= Y0 and ax0 + cw <= X1 and ay0 + ch <= Y1:
            mask[wy0:wy1, wx0:wx1][labels == i] = 255
            kept += 1
    if kept == 0:
        return None, 0
    k = max(3, int(round(5 * sx)) | 1)
    mask = cv2.dilate(mask, np.ones((k, k), np.uint8))
    out = cv2.inpaint(img, mask, max(3, int(4 * sx)), cv2.INPAINT_TELEA)
    return out, kept


def key_for(set_code, pid, variant):
    return f"cards/{set_code}/wotc_exact/TCGCSV_{pid}_{variant}_nostamp.jpg"


# Work list: every N/H row in these sets whose card has a 1st Edition (FE) row.
fe_by_pid = {
    p.tcgcsv_product_id: p for p in PokemonProduct.objects.filter(
        card_set__code__in=SETS, variant_override="FE", tcgcsv_product_id__isnull=False
    ).select_related("card_set")
}
targets = {}
for p in PokemonProduct.objects.filter(card_set__code__in=SETS, variant_override__in=["N", "H"],
                                       tcgcsv_product_id__in=list(fe_by_pid)).select_related("card_set"):
    targets.setdefault((p.card_set.code, p.tcgcsv_product_id, p.variant_override), []).append(p)

print(f"{'FORCE ' if FORCE else ''}{'PASS 2 ' if PASS2 else ''}{'LIVE' if LIVE else 'PREVIEW'} -- {len(targets)} card images to make "
      f"({sum(len(v) for v in targets.values())} rows)")

if not LIVE:
    os.makedirs("stamp_preview", exist_ok=True)
html = ["<html><body style='background:#222;color:#ddd;font:13px sans-serif'><h2>Stamp removal preview (before | after)</h2>"]

done = already = 0
skipped, failed, to_update = [], [], []
skipped_keys = []
for n_i, ((set_code, pid, variant), rows) in enumerate(sorted(targets.items()), 1):
    new_url = f"{PUBLIC_URL}/{key_for(set_code, pid, variant)}"
    if not FORCE and all(r.image_url == new_url for r in rows):
        already += 1
        continue
    if not LIVE and done >= PREVIEW_LIMIT:
        break
    fe = fe_by_pid[pid]
    img = fetch(fe.image_url)
    if img is None:
        failed.append((set_code, rows[0].name, "download failed", fe.image_url))
        continue
    if pid in NO_STAMP_IN_SCAN:
        score, x, y, size, out = 1.0, 0, 0, 0, img.copy()
    else:
        out = None
        score, x, y, size = find_stamp(img)
    if out is not None:
        pass
    elif PASS2 and score < ACCEPT and not (score >= ACCEPT_AT_SPOT and at_standard_spot(x, y)):
        skipped_keys.append((set_code, pid, variant)); skipped.append((set_code, rows[0].card_number, rows[0].name, f"pass2 score {score:.2f} at x{x} y{y}"))
        continue
    elif not PASS2 and not (score >= ACCEPT or (score >= ACCEPT_IN_ZONE and in_zone(x, y))):
        skipped_keys.append((set_code, pid, variant)); skipped.append((set_code, rows[0].card_number, rows[0].name, f"score {score:.2f} at x{x} y{y}"))
        continue
    if out is None:
        out, kept = remove_stamp(img, x, y, size)
        if out is None:
            skipped_keys.append((set_code, pid, variant)); skipped.append((set_code, rows[0].card_number, rows[0].name, "stamp found but no ink isolated"))
            continue
        # Safety check: the stamp must really be gone from that spot.
        after = find_stamp(out)
        if after[0] >= ACCEPT and abs(after[1] - x) < 12 and abs(after[2] - y) < 12:
            skipped_keys.append((set_code, pid, variant)); skipped.append((set_code, rows[0].card_number, rows[0].name, f"stamp still detected after removal ({after[0]:.2f})"))
            continue

    if not LIVE:
        H, W = img.shape[:2]
        sx, sy = W / NW, H / NH
        x0, y0 = max(0, int((x - 50) * sx)), max(0, int((y - 35) * sy))
        x1, y1 = min(W, int((x + size + 50) * sx)), min(H, int((y + size + 35) * sy))
        pair = np.hstack([img[y0:y1, x0:x1], out[y0:y1, x0:x1]])
        pair = cv2.resize(pair, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        fn = f"{set_code}_{rows[0].card_number}_{pid}_{variant}.jpg"
        cv2.imwrite(os.path.join("stamp_preview", fn), pair)
        full = f"{set_code}_{rows[0].card_number}_{pid}_{variant}_full.jpg"
        cv2.imwrite(os.path.join("stamp_preview", full), out)
        html.append(f"<div style='display:inline-block;margin:6px'><div>{set_code} #{rows[0].card_number} "
                    f"{rows[0].name} ({variant}) score {score:.2f}</div><a href='{full}'><img src='{fn}' height='160'></a></div>")
        done += 1
        continue

    ok, buf = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 92])
    try:
        s3.put_object(Bucket=R2_BUCKET, Key=key_for(set_code, pid, variant), Body=buf.tobytes(), ContentType="image/jpeg")
    except Exception as e:
        failed.append((set_code, rows[0].name, f"R2: {e}", ""))
        continue
    for r in rows:
        r.image_url = new_url
        r.image_small_url = new_url
        to_update.append(r)
    done += 1
    if len(to_update) >= 50:
        connection.ensure_connection()
        PokemonProduct.objects.bulk_update(to_update, ["image_url", "image_small_url"], batch_size=200)
        to_update = []
        print(f"  ...{n_i}/{len(targets)} done={done} skipped={len(skipped)} failed={len(failed)}")
    time.sleep(0.05)

if to_update:
    PokemonProduct.objects.bulk_update(to_update, ["image_url", "image_small_url"], batch_size=200)

# FORCE: a card this run could not confirm, but which an earlier run already
# changed, goes back to its untouched 1st Edition scan -- a stamped picture
# is better than one that may have had the wrong spot painted out.
reverted = 0
if FORCE and LIVE:
    back = []
    for key in skipped_keys:
        fe_url = fe_by_pid[key[1]].image_url
        for r in targets[key]:
            if r.image_url.endswith("_nostamp.jpg"):
                r.image_url = fe_url
                r.image_small_url = fe_url
                back.append(r)
    if back:
        PokemonProduct.objects.bulk_update(back, ["image_url", "image_small_url"], batch_size=200)
    reverted = len(back)
    print(f"Reverted to the 1st Edition scan (not confirmed this run): {reverted}")

if not LIVE:
    html.append("<h3>Skipped (no clear stamp found)</h3><pre>" + "\n".join(map(str, skipped)) + "</pre></body></html>")
    with open(os.path.join("stamp_preview", "index.html"), "w", encoding="utf-8") as f:
        f.write("\n".join(html))
    print("Preview written: open stamp_preview\\index.html")

print(f"\n{'LIVE' if LIVE else 'PREVIEW'} DONE | {'updated' if LIVE else 'previewed'}={done} "
      f"already-done={already} skipped={len(skipped)} failed={len(failed)}")
for s in skipped[:60]:
    print("  SKIPPED", s)
for f in failed[:40]:
    print("  FAILED", f)
