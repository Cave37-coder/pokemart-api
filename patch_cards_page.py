with open(r"C:\Users\texca\pokemart-frontend\src\app\cards\page.tsx", encoding="utf-8") as f:
    content = f.read()

marker = "const SUPERTYPES = ["
idx = content.index(marker)
tail = content[idx:]

with open(r"C:\Users\texca\pokemart-api\cards_page_header.tsx", encoding="utf-8") as f:
    new_header = f.read()

with open(r"C:\Users\texca\pokemart-frontend\src\app\cards\page.tsx", "w", encoding="utf-8") as f:
    f.write(new_header + "\n\n" + tail)

print("Done - page.tsx updated")
