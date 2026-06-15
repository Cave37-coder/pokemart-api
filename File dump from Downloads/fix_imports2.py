with open("products/views.py", encoding="utf-8") as f:
    content = f.read()

if "from django.db.models import Case" not in content:
    content = content.replace(
        "from django.db.models import Count",
        "from django.db.models import Count, Case, When, IntegerField"
    )
    with open("products/views.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("Done")
else:
    print("Already imported")
