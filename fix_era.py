with open("products/views.py", encoding="utf-8") as f:
    content = f.read()

content = content.replace(
    "eras = Era.objects.prefetch_related('cardset_set').order_by('code')",
    "eras = Era.objects.prefetch_related('sets').order_by('code')"
)

with open("products/views.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Done")
