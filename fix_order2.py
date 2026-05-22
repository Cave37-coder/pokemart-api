with open("products/views.py", encoding="utf-8") as f:
    content = f.read()

content = content.replace(
    'sets = CardSet.objects.select_related("era").annotate(card_count=Count("products")).order_by("-release_date")',
    'sets = CardSet.objects.select_related("era").annotate(card_count=Count("products")).order_by("-release_date", "name")'
)

with open("products/views.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Done")
