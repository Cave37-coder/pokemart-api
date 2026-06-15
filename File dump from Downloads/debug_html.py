import os, sys, django
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
sys.path.insert(0, ".")
django.setup()

from django.test import RequestFactory
from products.views import stock_entry

factory = RequestFactory()
request = factory.get("/api/stock/entry/", {"set": "POR"})
request.user = type("U", (), {"is_staff": True, "is_active": True})()

response = stock_entry(request)
html = response.content.decode()

# Find first few rows
start = html.find("<tbody>")
print(html[start:start+1000])
