with open("products/views.py", encoding="utf-8") as f:
    content = f.read()

content = content.replace(
    'sets = CardSet.objects.select_related("era").order_by("era__code", "name")',
    'sets = CardSet.objects.select_related("era").order_by("-release_date")'
)
content = content.replace(
    'eras = Era.objects.prefetch_related("sets").order_by("code")',
    'eras = Era.objects.prefetch_related("sets").order_by("-sets__release_date")'
)

with open("products/views.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Done")
