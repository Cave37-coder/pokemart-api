from products.models import PokemonProduct, CardSet

pp = CardSet.objects.get(id=143)  # PRIZEPACK

broken = PokemonProduct.objects.filter(
    card_set=pp,
    image_url__startswith='https://images.pokebulk.co.za/cards/PRIZEPACK/'
)
total = PokemonProduct.objects.filter(card_set=pp).count()
print(f"Total products in PRIZEPACK: {total}")
print(f"Products with broken R2 image_url: {broken.count()}")

# Break down by pb_id pattern, since that determines how we can fix each one
tcgcsv_sourced = broken.filter(pb_id__startswith='TCGCSV-')
manual_sourced = broken.exclude(pb_id__startswith='TCGCSV-')

print(f"\n  TCGCSV-sourced (pb_id='TCGCSV-{{id}}', can rebuild CDN URL directly): {tcgcsv_sourced.count()}")
print(f"  Manually-created (other pb_id pattern, no tcgcsv id to rebuild from): {manual_sourced.count()}")

print("\n--- Sample of manually-created broken rows (need a different fix) ---")
for p in manual_sourced[:20]:
    print(f"  id={p.id} pb_id={p.pb_id} tcgplayer_id={p.tcgplayer_id!r} card_number={p.card_number} name={p.name!r}")

print(f"\n--- Sample of TCGCSV-sourced broken rows (first 10 of {tcgcsv_sourced.count()}) ---")
for p in tcgcsv_sourced[:10]:
    print(f"  id={p.id} pb_id={p.pb_id} card_number={p.card_number} name={p.name!r}")

# Also check: are there any PRIZEPACK products whose image_url is fine (not broken),
# to confirm the working ones (like Galvantula etc. seen in the checklist) use a
# different source entirely
working = PokemonProduct.objects.filter(card_set=pp).exclude(
    image_url__startswith='https://images.pokebulk.co.za/cards/PRIZEPACK/'
)
print(f"\nProducts in PRIZEPACK with a DIFFERENT (working?) image_url pattern: {working.count()}")
for p in working[:10]:
    print(f"  id={p.id} pb_id={p.pb_id} image_url={p.image_url!r} name={p.name!r}")
