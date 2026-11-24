"""Models for Customer Management and Device/Equipment Registry."""

from django.db import models
from django.urls import reverse


class Customer(models.Model):
    """Customer profile representing an individual or business seeking service."""

    name = models.CharField(
        max_length=150,
        db_index=True,
        help_text="Full name or company name.",
    )
    phone = models.CharField(
        max_length=20,
        db_index=True,
        help_text="Primary contact phone number.",
    )
    email = models.EmailField(
        blank=True,
        help_text="Optional contact email address.",
    )
    address = models.TextField(
        blank=True,
        help_text="Physical or billing address.",
    )
    notes = models.TextField(
        blank=True,
        help_text="Internal notes about the customer (preferences, VIP status, etc.).",
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Designates whether this customer is actively serviced or archived.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Customer"
        verbose_name_plural = "Customers"
        indexes = [
            models.Index(fields=["name", "phone"], name="customer_name_phone_idx"),
        ]

    def __str__(self):
        return f"{self.name} ({self.phone})"

    def get_absolute_url(self):
        return reverse("customers:customer_detail", kwargs={"pk": self.pk})

    @property
    def total_devices(self):
        return self.devices.filter(is_active=True).count()


class Device(models.Model):
    """Physical device or piece of equipment submitted by a customer for repair."""

    class Category(models.TextChoices):
        LAPTOP = "laptop", "Laptop"
        DESKTOP = "desktop", "Desktop / PC"
        SMARTPHONE = "smartphone", "Smartphone"
        TABLET = "tablet", "Tablet"
        PRINTER = "printer", "Printer"
        NETWORKING = "networking", "Networking Equipment"
        OTHER = "other", "Other Equipment"

    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="devices",
        help_text="Customer who owns this equipment. Deletion is protected to preserve service history.",
    )
    category = models.CharField(
        max_length=50,
        choices=Category.choices,
        default=Category.LAPTOP,
    )
    brand = models.CharField(
        max_length=100,
        help_text="Manufacturer/Brand (e.g., Apple, Dell, Lenovo, Samsung).",
    )
    model = models.CharField(
        max_length=100,
        help_text="Model name or number (e.g., MacBook Pro 16, Inspiron 15 3000).",
    )
    serial_number = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="Unique serial number, Service Tag, or IMEI (if available).",
    )
    condition_at_intake = models.TextField(
        blank=True,
        help_text="Pre-existing physical condition (scratches, dents, cracks, missing screws).",
    )
    accessories_received = models.CharField(
        max_length=255,
        blank=True,
        help_text="Accessories handed in with the item (e.g., Power Adapter, Bag, Cable).",
    )
    customer_reported_issue = models.TextField(
        help_text="The malfunction or problem reported by the customer during intake.",
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Designates whether this device is active for service or decommissioned.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Device"
        verbose_name_plural = "Devices"
        indexes = [
            models.Index(fields=["brand", "model"], name="device_brand_model_idx"),
            models.Index(fields=["serial_number"], name="device_serial_idx"),
        ]

    def __str__(self):
        serial_str = f" [SN: {self.serial_number}]" if self.serial_number else ""
        return f"{self.brand} {self.model}{serial_str} - {self.customer.name}"

    def get_absolute_url(self):
        return reverse("customers:device_detail", kwargs={"pk": self.pk})
