with open('products/management/commands/enrich_only.py', 'r') as f:
    content = f.read()

old = "    product.pokedex_number   = pokedex_number\n        product.weakness_type"
new = "    product.pokedex_number   = pokedex_number\n        product.legal_standard   = legal_standard\n        product.legal_expanded   = legal_expanded\n        product.legal_unlimited  = legal_unlimited\n        product.weakness_type"

if old in content:
    content = content.replace(old, new)
    print("Done")
else:
    idx = content.find('product.pokedex_number')
    print(repr(content[idx-4:idx+80]))

with open('products/management/commands/enrich_only.py', 'w') as f:
    f.write(content)
