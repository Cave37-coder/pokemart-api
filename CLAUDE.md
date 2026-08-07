# Project rules

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
