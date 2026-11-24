"""URL routing for Service Tickets and Assignments."""

from django.urls import path
from . import views

app_name = "tickets"

urlpatterns = [
    path("", views.TicketListView.as_view(), name="ticket_list"),
    path("new/", views.TicketCreateView.as_view(), name="ticket_create"),
    path("<int:pk>/", views.TicketDetailView.as_view(), name="ticket_detail"),
    path("<int:pk>/edit/", views.TicketUpdateView.as_view(), name="ticket_update"),
    path("<int:pk>/assign/", views.TicketAssignView.as_view(), name="ticket_assign"),
    path("api/customer-devices/<int:customer_id>/", views.customer_devices_json, name="customer_devices_api"),
]
