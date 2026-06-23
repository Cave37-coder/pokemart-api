from products.models import PokemonProduct, CardSet

DRY_RUN = False  # confirmed via dry run — applying now

pp = CardSet.objects.get(id=143)  # PRIZEPACK

broken = PokemonProduct.objects.filter(
    card_set=pp,
    image_url__startswith='https://images.pokebulk.co.za/cards/PRIZEPACK/',
    pb_id__startswith='TCGCSV-',
)

print(f"Found {broken.count()} products to fix.")

to_update = []
sample_shown = 0
for p in broken:
    tcgcsv_id = p.pb_id.replace('TCGCSV-', '', 1)
    new_url = f"https://tcgplayer-cdn.tcgplayer.com/product/{tcgcsv_id}_200w.jpg"
    if sample_shown < 15:
        print(f"  id={p.id} name={p.name!r}")
        print(f"    old: {p.image_url!r}")
        print(f"    new: {new_url!r}")
        sample_shown += 1
    p.image_url = new_url
    p.image_small_url = new_url
    to_update.append(p)

if len(to_update) > sample_shown:
    print(f"  ... and {len(to_update) - sample_shown} more (not printed)")

if DRY_RUN:
    print(f"\nDRY RUN — nothing changed. {len(to_update)} rows would be updated. Set DRY_RUN = False and rerun to apply.")
else:
    PokemonProduct.objects.bulk_update(to_update, ['image_url', 'image_small_url'], batch_size=200)
    print(f"\nUpdated {len(to_update)} products.")
