import os, sys, django
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
sys.path.insert(0, os.getcwd())
django.setup()

import requests
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model

User = get_user_model()
u = User.objects.get(username="ashketchum")
refresh = RefreshToken.for_user(u)
token = str(refresh.access_token)

r = requests.post(
    "http://127.0.0.1:8000/api/cart/add/",
    json={"product_id": 46715, "quantity": 1},
    headers={"Authorization": f"Bearer {token}"}
)
print(f"Status: {r.status_code}")
print(f"Response: {r.text}")
