"""Models for Service Tickets, Technician Assignments, and Lifecycle Tracking."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
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

    def __str__(self):
        return f"{self.ticket_number} - {self.device.brand} {self.device.model} ({self.get_status_display()})"

    def clean(self):
        super().clean()
        # Business Rule: Device must belong to the selected customer
        if self.device_id and self.customer_id:
            if self.device.customer_id != self.customer_id:
                raise ValidationError(
                    {"device": f"The device '{self.device.brand} {self.device.model}' does not belong to {self.customer.name}."}
                )

        # Business Rule: Inactive technician cannot receive an assignment
        if self.assigned_technician_id and not self.assigned_technician.is_active:
            raise ValidationError(
                {"assigned_technician": f"Cannot assign ticket to '{self.assigned_technician.username}' because this technician account is inactive."}
            )

    def save(self, *args, **kwargs):
        if not self.ticket_number:
            from .services import generate_ticket_number
            self.ticket_number = generate_ticket_number()
        self.full_clean()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("tickets:ticket_detail", kwargs={"pk": self.pk})

    def assign_to(self, technician, assigned_by, notes=""):
        """Assigns the ticket to a technician and logs in assignment history."""
        if not technician.is_active:
            raise ValidationError(f"Cannot assign job to inactive user: {technician.username}")

        with transaction.atomic():
            # Mark previous active assignments as not current
            self.assignments.filter(is_current=True).update(is_current=False)

            # Create new assignment record
            Assignment.objects.create(
                ticket=self,
                technician=technician,
                assigned_by=assigned_by,
                notes=notes,
                is_current=True,
            )

            self.assigned_technician = technician
            self.save(update_fields=["assigned_technician", "updated_at"])


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
