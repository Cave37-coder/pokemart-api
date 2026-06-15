import re

with open("products/migrations/0010_pokemonproduct_tcgcsv_product_id.py") as f:
    content = f.read()

print("Current dependencies in 0010:")
deps = re.findall(r"dependencies = \[(.*?)\]", content, re.DOTALL)
print(deps)
