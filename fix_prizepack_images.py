from products.models import PokemonProduct

DRY_RUN = True  # review the printed list, then set False and rerun

# id -> tcgcsv product_id (confirmed via the bible CSV)
fixes = {
    405723: 677422,  # Basic Grass Energy - MEE001
    405724: 677423,  # Basic Fire Energy - MEE002
    405725: 677424,  # Basic Water Energy - MEE003
    405726: 677425,  # Basic Lightning Energy - MEE004
    405727: 677426,  # Basic Psychic Energy - MEE005
    405728: 677427,  # Basic Fighting Energy - MEE006
    405729: 677428,  # Basic Darkness Energy - MEE007
    405730: 677429,  # Basic Metal Energy - MEE008
}

print(f"Fixing image_url on {len(fixes)} PRIZEPACK products:")
for pid, tcgcsv_product_id in fixes.items():
    p = PokemonProduct.objects.get(id=pid)
    new_url = f"https://tcgplayer-cdn.tcgplayer.com/product/{tcgcsv_product_id}_200w.jpg"
    print(f"  id={p.id} name={p.name!r}")
    print(f"    old: {p.image_url!r}")
    print(f"    new: {new_url!r}")
    if not DRY_RUN:
        p.image_url = new_url
        p.image_small_url = new_url
        p.save(update_fields=['image_url', 'image_small_url'])

if DRY_RUN:
    print("\nDRY RUN — nothing changed. Set DRY_RUN = False and rerun to apply.")
else:
    print(f"\nUpdated image_url/image_small_url on {len(fixes)} products.")
