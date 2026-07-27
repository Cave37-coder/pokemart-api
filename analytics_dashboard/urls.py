# analytics_dashboard/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("summary/", views.dashboard_summary, name="analytics-dashboard-summary"),
]
