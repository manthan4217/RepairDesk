"""URL routing for Customers and Devices."""

from django.urls import path
from . import views

app_name = "customers"

urlpatterns = [
    # Customer routes
    path("", views.CustomerListView.as_view(), name="customer_list"),
    path("new/", views.CustomerCreateView.as_view(), name="customer_create"),
    path("<int:pk>/", views.CustomerDetailView.as_view(), name="customer_detail"),
    path("<int:pk>/edit/", views.CustomerUpdateView.as_view(), name="customer_update"),
    path("<int:pk>/toggle-status/", views.CustomerToggleStatusView.as_view(), name="customer_toggle_status"),

    # Device routes
    path("devices/", views.DeviceListView.as_view(), name="device_list"),
    path("devices/new/", views.DeviceCreateView.as_view(), name="device_create"),
    path("devices/<int:pk>/", views.DeviceDetailView.as_view(), name="device_detail"),
    path("devices/<int:pk>/edit/", views.DeviceUpdateView.as_view(), name="device_update"),
]
