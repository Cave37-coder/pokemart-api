with open("products/views.py", encoding="utf-8") as f:
    content = f.read()

content = content.replace(
    "ordering = ['-card_set__release_date', 'card_number']",
    "ordering = ['-card_set__release_date', 'card_number']"
)

with open("products/views.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Done - API already ordered by release date")
