"""URL routing for Dashboard, Search, and Reports."""

from django.urls import path
from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.DashboardOverviewView.as_view(), name="overview"),
    path("search/", views.GlobalSearchView.as_view(), name="search"),
    path("reports/", views.ReportsView.as_view(), name="reports"),
]
