"""Django Admin registration for Service Tickets, Assignments, Notes, and Completion Reports."""

from django.contrib import admin
from .models import Assignment, Attachment, CompletionReport, RepairUpdate, ServiceTicket, StatusHistory


class AssignmentInline(admin.TabularInline):
    model = Assignment
    extra = 0
    readonly_fields = ("technician", "assigned_by", "assigned_at", "notes", "is_current")
    can_delete = False


class RepairUpdateInline(admin.TabularInline):
    model = RepairUpdate
    extra = 0
    readonly_fields = ("author", "update_type", "notes", "created_at")
    can_delete = False


class StatusHistoryInline(admin.TabularInline):
    model = StatusHistory
    extra = 0
    readonly_fields = ("old_status", "new_status", "changed_by", "changed_at", "reason")
    can_delete = False


class AttachmentInline(admin.TabularInline):
    model = Attachment
    extra = 0
    readonly_fields = ("uploaded_by", "created_at")


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
    inlines = [AssignmentInline, RepairUpdateInline, StatusHistoryInline, AttachmentInline]


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("ticket", "technician", "assigned_by", "assigned_at", "is_current")
    list_filter = ("is_current", "assigned_at")
    search_fields = ("ticket__ticket_number", "technician__username", "assigned_by__username")
    readonly_fields = ("assigned_at",)


@admin.register(RepairUpdate)
class RepairUpdateAdmin(admin.ModelAdmin):
    list_display = ("ticket", "update_type", "author", "created_at")
    list_filter = ("update_type", "created_at")
    search_fields = ("ticket__ticket_number", "author__username", "notes")
    readonly_fields = ("created_at",)


@admin.register(StatusHistory)
class StatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("ticket", "old_status", "new_status", "changed_by", "changed_at")
    list_filter = ("new_status", "changed_at")
    search_fields = ("ticket__ticket_number", "changed_by__username", "reason")
    readonly_fields = ("changed_at",)


@admin.register(CompletionReport)
class CompletionReportAdmin(admin.ModelAdmin):
    list_display = ("ticket", "technician", "completed_at")
    search_fields = ("ticket__ticket_number", "technician__username", "diagnosis_summary", "work_performed")
    readonly_fields = ("completed_at",)


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ("ticket", "caption", "uploaded_by", "created_at")
    list_filter = ("created_at",)
    search_fields = ("ticket__ticket_number", "caption", "uploaded_by__username")
    readonly_fields = ("created_at",)

