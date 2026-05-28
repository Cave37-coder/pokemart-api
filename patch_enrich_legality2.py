with open('products/management/commands/enrich_only.py', 'r') as f:
    content = f.read()

found_all = True

# 1. Add legality extraction after artist line
old1 = "        artist          = card.get(\"artist\", \"\") or \"\""
new1 = "        artist          = card.get(\"artist\", \"\") or \"\"\n          legalities      = card.get(\"legalities\", {})\n          legal_standard  = True if legalities.get(\"standard\",\"\").lower()==\"legal\" else (False if legalities.get(\"standard\") else None)\n          legal_expanded  = True if legalities.get(\"expanded\",\"\").lower()==\"legal\" else (False if legalities.get(\"expanded\") else None)\n          legal_unlimited = legalities.get(\"unlimited\",\"\").lower()==\"legal\""

if old1 in content:
    content = content.replace(old1, new1)
    print("1. Legality extraction added")
else:
    print("1. NOT FOUND")
    found_all = False

# 2. Add legality to product fields assignment
old2 = "          product.pokedex_number   = pokedex_number"
new2 = "          product.pokedex_number   = pokedex_number\n          product.legal_standard   = legal_standard\n          product.legal_expanded   = legal_expanded\n          product.legal_unlimited  = legal_unlimited"

if old2 in content:
    content = content.replace(old2, new2)
    print("2. Legality assignment added")
else:
    print("2. NOT FOUND")
    found_all = False

# 3. Add to bulk_update FIELDS list
old3 = "            'hp', 'artist', 'flavour_text', 'pokedex_number',"
new3 = "            'hp', 'artist', 'flavour_text', 'pokedex_number',\n              'legal_standard', 'legal_expanded', 'legal_unlimited',"

if old3 in content:
    content = content.replace(old3, new3)
    print("3. Fields list updated")
else:
    print("3. NOT FOUND")
    found_all = False

# 4. After bulk_update, propagate legality to variants not found in API
# Find where "not found" products are handled and add propagation after the bulk_update
old4 = "    # Propagate legality from N variant to all other variants of same card"
if old4 in content:
    print("4. Propagation already added")
else:
    # Add after the bulk_update block - find the return statement
    old4b = "    return updated, not_found"
    new4b = """    # Propagate legality from any found variant to all variants of same card/set
    from django.db.models import Q
    cards_with_legality = PokemonProduct.objects.filter(
        card_set__code=set_code,
        legal_standard__isnull=False
    ).values('card_number', 'legal_standard', 'legal_expanded', 'legal_unlimited').distinct()
    
    propagated = 0
    for card in cards_with_legality:
        updated_count = PokemonProduct.objects.filter(
            card_set__code=set_code,
            card_number=card['card_number'],
            legal_standard__isnull=True
        ).update(
            legal_standard=card['legal_standard'],
            legal_expanded=card['legal_expanded'],
            legal_unlimited=card['legal_unlimited'],
        )
        propagated += updated_count
    
    if propagated:
        print(f"  Propagated legality to {propagated} variants")

    return updated, not_found"""

    if old4b in content:
        content = content.replace(old4b, new4b)
        print("4. Legality propagation added")
    else:
        print("4. return statement NOT FOUND")
        found_all = False

with open('products/management/commands/enrich_only.py', 'w') as f:
    f.write(content)

if found_all:
    print("\nAll patches applied successfully!")
else:
    print("\nSome patches failed - check output above")
