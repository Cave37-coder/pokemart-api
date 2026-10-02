from django.urls import path
from . import views

urlpatterns = [
    path("public-key/", views.public_key, name="push-public-key"),
    path("subscribe/", views.subscribe, name="push-subscribe"),
    path("unsubscribe/", views.unsubscribe, name="push-unsubscribe"),
    path("test/", views.send_test, name="push-test"),
]
