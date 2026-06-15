with open('products/management/commands/enrich_only.py', 'r') as f:
    content = f.read()

# Add legality extraction after artist
old = """        artist          = card.get("artist", "") or ""
          flavour_text    = card.get("flavorText", "") or """""

new = """        artist          = card.get("artist", "") or ""
          flavour_text    = card.get("flavorText", "") or ""
          legalities      = card.get("legalities", {})
          legal_standard  = True if legalities.get("standard", "").lower() == "legal" else (False if legalities.get("standard") else None)
          legal_expanded  = True if legalities.get("expanded", "").lower() == "legal" else (False if legalities.get("expanded") else None)
          legal_unlimited = True if legalities.get("unlimited", "").lower() == "legal" else True"""

if old in content:
    content = content.replace(old, new)
    print("Legality extraction added")
else:
    print("NOT FOUND - extraction")

# Add legality assignment after pokedex_number
old2 = """          product.pokedex_number   = pokedex_number"""
new2 = """          product.pokedex_number   = pokedex_number
          product.legal_standard   = legal_standard
          product.legal_expanded   = legal_expanded
          product.legal_unlimited  = legal_unlimited"""

if old2 in content:
    content = content.replace(old2, new2)
    print("Legality assignment added")
else:
    print("NOT FOUND - assignment")

# Add to bulk_update fields
old3 = """            'image_url', 'image_small_url', 'supertype', 'card_subtypes',
              'hp', 'artist', 'flavour_text', 'pokedex_number',"""
new3 = """            'image_url', 'image_small_url', 'supertype', 'card_subtypes',
              'hp', 'artist', 'flavour_text', 'pokedex_number',
              'legal_standard', 'legal_expanded', 'legal_unlimited',"""

if old3 in content:
    content = content.replace(old3, new3)
    print("Legality fields added to bulk_update")
else:
    print("NOT FOUND - bulk_update")

with open('products/management/commands/enrich_only.py', 'w') as f:
    f.write(content)
