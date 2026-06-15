with open("products/views.py", encoding="utf-8") as f:
    content = f.read()

content = content.replace(
    ".order_by('card_number', 'variant_override')",
    ".annotate(var_order=Case(When(variant_override='N',then=0),When(variant_override='RH',then=1),When(variant_override='H',then=2),default=3,output_field=IntegerField())).order_by('card_number','var_order')"
)

with open("products/views.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Done")
