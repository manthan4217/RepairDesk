"""Models for Service Tickets, Technician Assignments, Repair Updates, and Completion Reports."""

import os
import random
import time
import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import IntegrityError, models, transaction
from django.urls import reverse

from apps.customers.models import Customer, Device


class ServiceTicket(models.Model):
    """Core repair request tracking equipment from intake to completion."""

    class Status(models.TextChoices):
        RECEIVED = "received", "Received"
        UNDER_DIAGNOSIS = "under_diagnosis", "Under Diagnosis"
        IN_PROGRESS = "in_progress", "In Progress"
        ON_HOLD = "on_hold", "On Hold"
        COMPLETED = "completed", "Completed"
        READY_FOR_DELIVERY = "ready_for_delivery", "Ready for Delivery"
        DELIVERED = "delivered", "Delivered / Closed"
        CANCELLED = "cancelled", "Cancelled"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    ALLOWED_TRANSITIONS = {
        Status.RECEIVED: [Status.UNDER_DIAGNOSIS, Status.IN_PROGRESS, Status.CANCELLED],
        Status.UNDER_DIAGNOSIS: [Status.IN_PROGRESS, Status.COMPLETED, Status.ON_HOLD, Status.CANCELLED],
        Status.IN_PROGRESS: [Status.COMPLETED, Status.ON_HOLD, Status.CANCELLED],
        Status.ON_HOLD: [Status.IN_PROGRESS, Status.UNDER_DIAGNOSIS, Status.CANCELLED],
        Status.COMPLETED: [Status.READY_FOR_DELIVERY, Status.IN_PROGRESS],
        Status.READY_FOR_DELIVERY: [Status.DELIVERED, Status.COMPLETED],
        Status.DELIVERED: [],
        Status.CANCELLED: [],
    }

    ticket_number = models.CharField(
        max_length=32,
        unique=True,
        db_index=True,
        editable=False,
        help_text="Unique collision-safe human-readable ticket number (e.g. RD-2026-00001).",
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="tickets",
        help_text="The customer requesting this service.",
    )
    device = models.ForeignKey(
        Device,
        on_delete=models.PROTECT,
        related_name="tickets",
        help_text="The device or equipment undergoing repair.",
    )
    assigned_technician = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tickets",
        help_text="Current technician assigned to diagnose and execute this repair.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_tickets",
        help_text="Staff member who registered this ticket.",
    )
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.RECEIVED,
        db_index=True,
    )
    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.NORMAL,
        db_index=True,
    )
    issue_description = models.TextField(
        help_text="Detailed malfunction description, symptoms, and customer requests.",
    )
    estimated_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Preliminary price estimate provided to customer (if applicable).",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Service Ticket"
        verbose_name_plural = "Service Tickets"
        indexes = [
            models.Index(fields=["status", "priority"], name="ticket_status_priority_idx"),
            models.Index(fields=["created_at"], name="ticket_created_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        "received",
                        "under_diagnosis",
                        "in_progress",
                        "on_hold",
                        "completed",
                        "ready_for_delivery",
                        "delivered",
                        "cancelled",
                    ]
                ),
                name="ticket_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(priority__in=["low", "normal", "high", "urgent"]),
                name="ticket_priority_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(estimated_cost__gte=0) | models.Q(estimated_cost__isnull=True),
                name="ticket_estimated_cost_non_negative",
            ),
        ]

    def __str__(self):
        return f"{self.ticket_number} - {self.device.brand} {self.device.model} ({self.get_status_display()})"

    def clean(self):
        super().clean()
        if self.device_id and self.customer_id:
            if self.device.customer_id != self.customer_id:
                raise ValidationError(
                    {"device": f"The device '{self.device.brand} {self.device.model}' does not belong to {self.customer.name}."}
                )

        if self.assigned_technician_id:
            if not self.assigned_technician.is_active:
                raise ValidationError(
                    {"assigned_technician": f"Cannot assign ticket to '{self.assigned_technician.username}' because this technician account is inactive."}
                )
            if not self.assigned_technician.is_technician:
                raise ValidationError(
                    {"assigned_technician": f"User '{self.assigned_technician.username}' is not a designated technician."}
                )

        if self.status in [self.Status.READY_FOR_DELIVERY, self.Status.DELIVERED]:
            if not (self.pk and hasattr(self, "completion_report")):
                raise ValidationError(
                    {"status": "A ticket cannot be marked Ready for Delivery or Closed without an approved Completion Report."}
                )

    def save(self, *args, **kwargs):
        if not self.ticket_number:
            from .services import generate_ticket_number
            max_retries = 10
            for attempt in range(max_retries):
                try:
                    with transaction.atomic():
                        self.ticket_number = generate_ticket_number()
                        self.full_clean()
                        super().save(*args, **kwargs)
                        break
                except (IntegrityError, ValidationError) as exc:
                    if isinstance(exc, ValidationError):
                        msg_dict = getattr(exc, "message_dict", {})
                        err_dict = getattr(exc, "error_dict", {})
                        is_ticket_err = "ticket_number" in msg_dict or "ticket_number" in err_dict
                    else:
                        err_msg = str(exc).lower()
                        is_ticket_err = "ticket_number" in err_msg or "duplicate entry" in err_msg or "1062" in err_msg

                    if is_ticket_err and attempt < max_retries - 1:
                        self.ticket_number = None
                        time.sleep(0.01 * (attempt + 1) + random.uniform(0.005, 0.02))
                        continue
                    raise
        else:
            self.full_clean()
            super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("tickets:ticket_detail", kwargs={"pk": self.pk})

    def assign_to(self, technician, assigned_by, notes=""):
        """Assigns the ticket to a technician and logs in assignment history with row lock."""
        if not technician.is_active:
            raise ValidationError(f"Cannot assign job to inactive user: {technician.username}")
        if not technician.is_technician:
            raise ValidationError(f"User '{technician.username}' is not a designated technician.")

        with transaction.atomic():
            locked_ticket = ServiceTicket.objects.select_for_update().get(pk=self.pk)
            locked_ticket.assignments.filter(is_current=True).update(is_current=False)
            Assignment.objects.create(
                ticket=locked_ticket,
                technician=technician,
                assigned_by=assigned_by,
                notes=notes,
                is_current=True,
            )
            locked_ticket.assigned_technician = technician
            locked_ticket.save(update_fields=["assigned_technician", "updated_at"])
            self.assigned_technician = technician

    def can_transition_to(self, new_status):
        """Checks if transitioning from current status to new_status is permitted."""
        if self.status == new_status:
            return True
        allowed = self.ALLOWED_TRANSITIONS.get(self.status, [])
        return new_status in allowed

    def update_status(self, new_status, user, reason=""):
        """Updates ticket status, enforces lifecycle rules, and records in StatusHistory with row lock."""
        if new_status == self.status:
            return

        # Check permitted transition (administrators have override capability for exceptional cases)
        if not self.can_transition_to(new_status) and not user.is_administrator:
            raise ValidationError(
                f"Invalid status transition from '{self.get_status_display()}' to '{dict(self.Status.choices).get(new_status)}'."
            )

        # Rule: Transition to Ready for Delivery or Delivered requires a Completion Report
        if new_status in [self.Status.READY_FOR_DELIVERY, self.Status.DELIVERED]:
            if not hasattr(self, "completion_report"):
                raise ValidationError(
                    "A ticket cannot be marked Ready for Delivery or Closed without an approved Completion Report."
                )

        with transaction.atomic():
            locked_ticket = ServiceTicket.objects.select_for_update().get(pk=self.pk)
            old_status = locked_ticket.status
            locked_ticket.status = new_status
            locked_ticket.save(update_fields=["status", "updated_at"])

            StatusHistory.objects.create(
                ticket=locked_ticket,
                old_status=old_status,
                new_status=new_status,
                changed_by=user,
                reason=reason,
            )
            self.status = new_status


class Assignment(models.Model):
    """Audit history of technician assignments for a service ticket."""

    ticket = models.ForeignKey(
        ServiceTicket,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    technician = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="technician_assignments",
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assigned_by_records",
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    notes = models.CharField(
        max_length=255,
        blank=True,
        help_text="Assignment instructions or reassignment rationale.",
    )
    is_current = models.BooleanField(
        default=True,
        help_text="Designates whether this assignment is the currently active one.",
    )

    class Meta:
        ordering = ["-assigned_at"]
        verbose_name = "Assignment"
        verbose_name_plural = "Assignments"

    def __str__(self):
        return f"{self.ticket.ticket_number} -> {self.technician.username} ({self.assigned_at.strftime('%Y-%m-%d')})"


class RepairUpdate(models.Model):
    """Diagnosis findings, repair progress notes, and parts logs recorded during servicing."""

    class UpdateType(models.TextChoices):
        DIAGNOSIS = "diagnosis", "Diagnosis Finding"
        PROGRESS = "progress", "Repair Progress"
        PARTS = "parts", "Parts Used / Required"
        GENERAL = "general", "General Note"

    ticket = models.ForeignKey(
        ServiceTicket,
        on_delete=models.CASCADE,
        related_name="updates",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="repair_updates",
    )
    update_type = models.CharField(
        max_length=20,
        choices=UpdateType.choices,
        default=UpdateType.PROGRESS,
    )
    notes = models.TextField(
        help_text="Technical notes on diagnostic findings, test results, or work performed.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Repair Update"
        verbose_name_plural = "Repair Updates"

    def __str__(self):
        return f"{self.get_update_type_display()} on {self.ticket.ticket_number} by {self.author.username}"


class StatusHistory(models.Model):
    """Audit trail of lifecycle status transitions for a service ticket."""

    ticket = models.ForeignKey(
        ServiceTicket,
        on_delete=models.CASCADE,
        related_name="status_history",
    )
    old_status = models.CharField(max_length=32)
    new_status = models.CharField(max_length=32)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="status_changes",
    )
    changed_at = models.DateTimeField(auto_now_add=True)
    reason = models.CharField(
        max_length=255,
        blank=True,
        help_text="Reason for hold, cancellation, or status change.",
    )

    class Meta:
        ordering = ["-changed_at"]
        verbose_name = "Status History"
        verbose_name_plural = "Status History"

    def __str__(self):
        return f"{self.ticket.ticket_number}: {self.old_status} -> {self.new_status} by {self.changed_by.username}"


class CompletionReport(models.Model):
    """Formal sign-off report submitted upon repair completion before device handover."""

    ticket = models.OneToOneField(
        ServiceTicket,
        on_delete=models.CASCADE,
        related_name="completion_report",
        help_text="The service ticket this report concludes.",
    )
    technician = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="completed_reports",
    )
    diagnosis_summary = models.TextField(
        help_text="Final confirmed root cause of the reported malfunction.",
    )
    work_performed = models.TextField(
        help_text="Comprehensive summary of repair steps, tests, and component servicing performed.",
    )
    parts_replaced = models.CharField(
        max_length=255,
        blank=True,
        help_text="Components, chips, or replacement parts installed (if applicable).",
    )
    technician_remarks = models.TextField(
        blank=True,
        help_text="Post-repair recommendations, preventive tips, or warranty notes for the customer.",
    )
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-completed_at"]
        verbose_name = "Completion Report"
        verbose_name_plural = "Completion Reports"

    def __str__(self):
        return f"Completion Report for {self.ticket.ticket_number} ({self.technician.username})"


def ticket_attachment_upload_path(instance, filename):
    """Generates a secure, collision-safe path for uploaded ticket attachments."""
    ext = os.path.splitext(filename)[1].lower()
    unique_filename = f"{uuid.uuid4().hex}{ext}"
    return os.path.join("ticket_attachments", instance.ticket.ticket_number, unique_filename)


class Attachment(models.Model):
    """Uploaded photos or documents (intake damage photos, schematics, logs) for a ticket."""

    ALLOWED_EXTENSIONS = ["jpg", "jpeg", "png", "webp", "pdf"]

    ticket = models.ForeignKey(
        ServiceTicket,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="uploaded_attachments",
    )
    file = models.FileField(
        upload_to=ticket_attachment_upload_path,
        validators=[FileExtensionValidator(allowed_extensions=ALLOWED_EXTENSIONS)],
        help_text="Upload an inspection image (JPG, PNG, WEBP) or PDF log. Max 5MB.",
    )
    caption = models.CharField(
        max_length=200,
        blank=True,
        help_text="Optional description (e.g. 'Intake cracked screen photo', 'Thermal test report')",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Attachment"
        verbose_name_plural = "Attachments"

    def __str__(self):
        return f"{self.caption or self.file.name} ({self.ticket.ticket_number})"

    @property
    def is_image(self):
        ext = os.path.splitext(self.file.name)[1].lower()
        return ext in [".jpg", ".jpeg", ".png", ".webp"]

