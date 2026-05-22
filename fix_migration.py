with open("products/migrations/0010_pokemonproduct_tcgcsv_product_id.py") as f:
    content = f.read()

content = content.replace(
    "('products', '0009_cardset_checklist_pdf_cardset_checklist_xlsx'),",
    "('products', '0008_pokemonproduct_csv_sku_alter_pokemonproduct_rarity_and_more'),"
)

with open("products/migrations/0010_pokemonproduct_tcgcsv_product_id.py", "w") as f:
    f.write(content)

print("Fixed 0010 dependency")
print()
with open("products/migrations/0010_pokemonproduct_tcgcsv_product_id.py") as f:
    print(f.read())
