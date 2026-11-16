# Project rules

## PowerShell git commands — always clear the stale index.lock first

Michael's Windows checkout keeps leaving behind a stale `.git\index.lock`
that blocks `git add`/`commit`/`push` — deleting it by hand hasn't stuck
(it comes back). Michael, 2026-08-17: "when powershell commands to run,
that you add the gitlock, that you delete... so if the delete can be added
automatically to all commands."

Whenever giving Michael a PowerShell git command sequence to run (in this
repo or `pokemart-frontend`), always prepend a line clearing the lock first
— every time, not just after a lock error has already shown up:

```powershell
Remove-Item -Force .git\index.lock -ErrorAction SilentlyContinue
git add <files>
git commit -m "..."
git push
```

## Big scripts — always build in a progress tracker

Michael, 2026-11-16: "all big scripts must have progress trackers built in!"
(after an overnight enrichment died when the laptop was closed and he couldn't
tell how far it had got).

Any management command / script that touches many rows, sets or network calls
(enrichment, syncs, bulk imports, backfills, image uploads) must have, built in:

1. A live progress line per step: `[done/total] %  <what>  elapsed  ETA`.
2. A progress file (e.g. `*_progress.txt`) he can open from another window,
   plus a `--status` flag that shows progress without running anything.
3. Resumability: save state after each finished unit (e.g. `*_progress.json`)
   so re-running the same command skips what's done and retries what failed.
   One failed item must never stop the whole run.
4. Retries for flaky network calls, and a final summary (done / failed / before→after).

Reference implementation: `products/management/commands/enrich_all_tracked.py`.

## Energy cards — release set in the name, one Energy set per era

Michael, 2026-11-16: every Energy card's name must include the set/product it
was released with, even when that's an Ultra-Premium Collection (e.g. the
Terapagos ex UPC "Cracked Ice Holo" Basic Energy, SVE 009-016). Energy lives in
one Energy set per era, with every variant and an R2-hosted image. Promo and
filler sets belong to their real era (BW, XY, SM ...), never the legacy B1-B9
era codes (`fix_promo_eras`). Audit with `audit_energy` before importing.

### Energy order (Michael, 2026-11-16 — implemented in `products/energy_order.py`)

Wherever basic Energies are listed (checklists, set views, buy-in/POS card lists, shop sorting) they must follow
this type order, then variants: 1 Grass, 2 Fire, 3 Water, 4 Lightning (Electric), 5 Psychic, 6 Fighting,
7 Darkness, 8 Fairy, 9 Metal (Steel), 10 Dragon, 11 Colorless. Dragon and Colorless are not official basic
Energies but have Special Energies, so they sort last. Release date still decides which set a card comes from;
this order applies within a set's basic Energies (and to the typed Special Energies, e.g. "Growing Grass").

## Image hosting — always R2, never external hotlinks

Every image URL stored anywhere on this site (set logos/symbols, era logos,
card images, accessory images, avatars, anything) must end up hosted on
Cloudflare R2, never left pointing at an external source (TCGCSV, Google
Images, Bulbapedia, etc.). Michael, 2026-08-08: "yes r2 always for images,
set in rules!"

- Bucket: `pokebulkcards`
- Public CDN domain: `https://images.pokebulk.co.za`
- Key convention: `<category>/<subcategory>/<identifier>.<ext>`, e.g.
  `sets/logos/{code}_logo.png`, `sets/symbols/{code}_symbol.png`,
  `eras/logos/{code}_logo.png`, `cards/{set_code}_{pid}_{variant}.jpg`

When adding any new feature that stores an image URL (a new model field, a
new import/sync command, etc.):

1. If the image is uploaded/synced programmatically (e.g. a management
   command pulling from TCGCSV), download it and upload straight to R2 as
   part of that same command — never save the external URL directly.
2. If the image URL is something a person pastes in manually via Django
   admin (like `Era.logo_url`), also add an admin action that re-hosts
   whatever's currently in the field to R2 on demand (see
   `products.admin.upload_logos_to_r2` for the reference implementation) —
   don't require every field to be re-hosted at save time, but make it a
   one-click action.
3. Reuse the `_r2_client()` credentials pattern already established across
   `upload_to_r2.py` / `upload_set_images.py` / `products/admin.py` rather
   than inventing a new one.
