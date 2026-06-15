import os, sys, django
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
sys.path.insert(0, os.getcwd())
django.setup()

from products.models import PokemonProduct

# Find a newly created card (no image)
new = PokemonProduct.objects.filter(image_url__isnull=True).select_related("card_set").first()
if not new:
    new = PokemonProduct.objects.filter(image_url="").select_related("card_set").first()

if new:
    print(f"Name:        {new.name}")
    print(f"Set:         {new.card_set.name}")
    print(f"Card number: {new.card_number}")
    print(f"Variant:     {new.variant_override}")
    print(f"Price:       R{new.price}")
    print(f"image_url:   {repr(new.image_url)}")
    print(f"HP:          {new.hp}")
    print(f"tcgcsv_id:   {new.tcgcsv_product_id}")
else:
    print("All cards have images!")
