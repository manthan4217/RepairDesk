"""Django Admin registration for Service Tickets and Assignments."""

from django.contrib import admin
from .models import Assignment, ServiceTicket


class AssignmentInline(admin.TabularInline):
    model = Assignment
    extra = 0
    readonly_fields = ("technician", "assigned_by", "assigned_at", "notes", "is_current")
    can_delete = False


@admin.register(ServiceTicket)
class ServiceTicketAdmin(admin.ModelAdmin):
    list_display = (
        "ticket_number",
        "customer",
        "device",
        "assigned_technician",
        "status",
        "priority",
        "created_at",
    )
    list_filter = ("status", "priority", "created_at")
    search_fields = (
        "ticket_number",
        "customer__name",
        "customer__phone",
        "device__brand",
        "device__model",
        "device__serial_number",
    )
    readonly_fields = ("ticket_number", "created_by", "created_at", "updated_at")
    inlines = [AssignmentInline]


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("ticket", "technician", "assigned_by", "assigned_at", "is_current")
    list_filter = ("is_current", "assigned_at")
    search_fields = ("ticket__ticket_number", "technician__username", "assigned_by__username")
    readonly_fields = ("assigned_at",)
