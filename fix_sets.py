with open("products/views.py", encoding="utf-8") as f:
    content = f.read()

content = content.replace(
    'sets = CardSet.objects.select_related("era").annotate(card_count=Count("products")).order_by("-release_date", "name")',
    'sets = list(CardSet.objects.select_related("era").annotate(card_count=Count("products")).order_by("-release_date", "name"))\nsets = [s for s in sets if s.card_count > 0] + [s for s in sets if s.card_count == 0]'
)

with open("products/views.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Done")
