with open(r"C:\Users\texca\pokemart-frontend\src\app\cards\page.tsx", encoding="utf-8") as f:
    content = f.read()

# Fix Pokemon supertype value to match DB
content = content.replace(
    '{ label: "Pokemon", value: "Pokemon" }',
    '{ label: "Pokemon", value: "Pok\\u00e9mon" }'
)

with open(r"C:\Users\texca\pokemart-frontend\src\app\cards\page.tsx", "w", encoding="utf-8") as f:
    f.write(content)

print("Fixed Pokemon supertype accent")
