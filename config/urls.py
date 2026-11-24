"""Root URL configuration for RepairDesk."""

from django.contrib import admin
from django.urls import include, path

from config.views import home

admin.site.site_header = "RepairDesk"
admin.site.site_title = "RepairDesk admin"
admin.site.index_title = "Administration"

urlpatterns = [
    path("", home, name="home"),
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
]
