"""URL routing for Service Tickets, Technician Workspace, Notes, and Completion Reports."""

from django.urls import path
from . import views

app_name = "tickets"

urlpatterns = [
    # Ticket overview & workspace
    path("", views.TicketListView.as_view(), name="ticket_list"),
    path("my-jobs/", views.MyJobsListView.as_view(), name="my_jobs"),

    # Ticket intake & management
    path("new/", views.TicketCreateView.as_view(), name="ticket_create"),
    path("<int:pk>/", views.TicketDetailView.as_view(), name="ticket_detail"),
    path("<int:pk>/edit/", views.TicketUpdateView.as_view(), name="ticket_update"),
    path("<int:pk>/assign/", views.TicketAssignView.as_view(), name="ticket_assign"),

    # Repair updates, lifecycle status, completion report
    path("<int:pk>/notes/new/", views.RepairUpdateCreateView.as_view(), name="repair_update_create"),
    path("<int:pk>/status/", views.TicketStatusTransitionView.as_view(), name="ticket_status_update"),
    path("<int:pk>/complete/", views.CompletionReportCreateView.as_view(), name="completion_report_create"),

    # Async helper API
    path("api/customer-devices/<int:customer_id>/", views.customer_devices_json, name="customer_devices_api"),
]
