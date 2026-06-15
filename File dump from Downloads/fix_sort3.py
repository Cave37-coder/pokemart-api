with open("products/views.py", encoding="utf-8") as f:
    content = f.read()

content = content.replace(
    "When(variant_override='N',then=0),When(variant_override='RH',then=1),When(variant_override='H',then=2)",
    "When(variant_override='N',then=1),When(variant_override='RH',then=2),When(variant_override='H',then=3)"
)

with open("products/views.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Done")
