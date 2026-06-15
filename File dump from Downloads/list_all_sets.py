import os, sys, django
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
sys.path.insert(0, ".")
django.setup()

from products.models import CardSet

print("All DB set codes:")
for s in CardSet.objects.order_by("code"):
    print(f"  {s.code:20} {s.name}")
