# 30th Celebration — API prep, what's ready and what's not

## What I've put in this folder

- `create_cardset_30th_celebration.py` — creates the two CardSet rows (`30C` main set, `30CC` Classic Collection), same pattern as `create_cardset_pbl.py`. Dry-run by default.
- `30C_bible_sheet.csv` — bible-format sheet, 19 rows. These are the ONLY 30th Celebration main-set cards with a confirmed real TCGCSV `product_id` right now.
- `30CC_bible_sheet.csv` — bible-format sheet, all 30 Classic Collection cards, fully populated with real `product_id`s and current market pricing (this subset's TCGCSV group is small enough that I could pull it completely).

## ✅ Rarity-mapping bugs — scanned and fixed (2026-09-16)

You asked me to scan for and fix anything that could cause rarity mistakes. I searched every `.py` file in the repo for rarity-mapping logic (`RARITY_MAP`, `RARITY_CHOICES`, and the specific terms involved) and found it in exactly four places. Three needed changes; I've made them and written the files straight back into your `pokemart-api` folder:

1. **`sync_bible_to_db.py`** — `RARITY_MAP` was mapping `"Double Rare"` → `"ultra_rare"`, even though `products/models.py` already has a dedicated `"double_rare"` choice (added 2026-09-11, specifically to stop this exact conflation — your own comment on that field explains the Lurantis ex bug it fixed). The map was never updated to match, so **every Double Rare card synced through this script — Pitch Black included — has been getting tagged `ultra_rare`, not `double_rare`, this whole time.** Fixed. Also added the two new tiers this set introduces: `"Pikachu Rare"` → `"pikachu_rare"` and `"Futuristic Rare"` → `"futuristic_rare"` — without these, `RARITY_MAP.get(rarity_raw, 'common')` would have silently filed all 30 chase Pikachus and both Futuristic Rares (your two most expensive cards, ~$830 and ~$1,800 market) under `"common"`.

2. **`sync_missing_variants.py`** — same exact `"double rare"` → `"ultra_rare"` bug, in its own separate copy of the map (this script has its own `RARITY_MAP`, doesn't share the one in `sync_bible_to_db.py`). Fixed the same way, plus added `"pikachu rare"` / `"futuristic rare"` preemptively in case this script is ever pointed at 30C. It's currently hardcoded to `TARGET_SETS = ['PRE', 'ASC', 'WHT', 'BLK']`, so this fix doesn't affect anything live right now, but it was carrying the same bug forward.

3. **`products/models.py`** — added the two missing `RARITY_CHOICES` entries: `("pikachu_rare", "Pikachu Rare")` and `("futuristic_rare", "Futuristic Rare")`. This is additive (new choices, nothing removed or renamed) and doesn't touch the DB column type, so it's safe at runtime even before a migration exists — but you should still run `python manage.py makemigrations products` once you're back on the machine, so migration state matches the model. **I couldn't run that myself** — see the mount issue below.

4. **`products/views.py`** — checked (it has its own `EX → "Double Rare"` style label dicts for the pull-sheet/stock-management pages), but those map an old `variant_override` short-code to a display string, not the rarity field, and 30th Celebration's cards don't use that short-code — no change needed there.

One more thing I noticed while scanning but did **not** touch, since it's unrelated to this set and I don't have enough context to know if it's already handled elsewhere: `RARITY_MAP` also maps `"Shiny Rare"` and `"Shiny Ultra Rare"` to `shiny_rare` / `shiny_ultra_rare`, but neither of those exists in `RARITY_CHOICES` either. Worth a look at some point, separate from 30th Celebration.

## Why only 19 of ~188 main-set cards have product_ids

TCGCSV's group for the main set (group_id 24722) now has 202 total products, but the fetch tool available to me in this chat hard-truncates that response after roughly 50-55 entries — it never reaches the ~150+ card products TCGCSV added around street date. I confirmed those newer product_ids exist (via the smaller `/prices` endpoint, which did come through complete) but couldn't get their names/numbers/rarities to build real rows.

**This is exactly what `sync_tcgcsv.py`-style direct fetching is for** — it makes a plain `requests.get()` from your own machine/server with no such size cap. The fastest path to a complete `30C_bible_sheet.csv` is running your normal TCGCSV export flow (`export_tcgcsv_bible.py` / `fetch_tcgcsv_all_v1.0.1.py`, whichever is your current one) filtered to group_id `24722`, then `merge_tcgcsv_to_bible_v1.0.1.py` to fold it into the bible. I couldn't run that here myself either — see below.

## Why I couldn't just run these scripts for you

Your computer is linked, but a Windows update from September 8 broke the folder-mount bridge this session normally uses to run shell commands directly on your machine — I can read and write files there, but I can't execute Python on it right now. Anthropic's aware of the issue. So: I built everything I could build blind, but the actual command sequence below needs to be run by you (or ask me again once the mount issue is fixed, and I can drive it directly).

## Suggested run order, once you're ready

```powershell
Remove-Item -Force .git\index.lock -ErrorAction SilentlyContinue
cd C:\Users\texca\pokemart-api

# 1. Generate the migration for the two new rarity choices (the fixes above are already in your files)
python manage.py makemigrations products
python manage.py migrate

# 2. Create the CardSets (dry run first)
python manage.py shell -c "exec(open('create_cardset_30th_celebration.py').read())"
$env:CARDSET_APPLY=1
python manage.py shell -c "exec(open('create_cardset_30th_celebration.py').read())"

# 3. Merge the two sheets I built into your real bible (adjust version numbers to whatever's current)
python merge_set_into_bible_v1.0.py --bible pokebulk_bible_v7_r2.csv --new 30C_bible_sheet.csv --set-code 30C --new-version 8 --dry-run
python merge_set_into_bible_v1.0.py --bible pokebulk_bible_v7_r2.csv --new 30C_bible_sheet.csv --set-code 30C --new-version 8
python merge_set_into_bible_v1.0.py --bible pokebulk_bible_v8.csv --new 30CC_bible_sheet.csv --set-code 30CC --new-version 9

# 4. Sync into the DB
python sync_bible_to_db.py --bible pokebulk_bible_v9.csv --set-code 30C --dry-run
python sync_bible_to_db.py --bible pokebulk_bible_v9.csv --set-code 30C
python sync_bible_to_db.py --bible pokebulk_bible_v9.csv --set-code 30CC

# 5. Once the full 202-product TCGCSV pull is done separately, re-run merge_tcgcsv_to_bible + sync again
#    to pick up the remaining ~150 main-set cards and real Reverse Holofoil/Holofoil variant data.

# 6. fix_total_cards.py, R2 image migration, Bulbapedia enrichment -- same as any other new set.
```

## Still open after all of the above

- Pricing here is USD market price from TCGCSV — `pokebulk_zar` is left blank in both sheets (would otherwise silently default to R1.50 via `to_decimal`'s fallback). Set real ZAR pricing through your normal stock-entry workflow before these go live, same as every other set.
- `final_image_url` is left blank — these need the same Bulbapedia-enrichment + R2-upload pass every other set gets before they're allowed to go live per your image-hosting rule in `CLAUDE.md`. Do not point live listings at the raw TCGplayer CDN URLs in the meantime.
- 4 secret rares (Kommo-o #143, Mewtwo ex SIR #151, Mew ex SIR #152, Gengar ex SIR #154) are name-confirmed on Serebii but have no card image yet — normal, just not ready to enrich yet.
- The 8 Basic Energy cards and the "Premium Deck Set: Espeon & Umbreon" sibling product are still unitemized.
