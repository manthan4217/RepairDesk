"""Django Admin registration for Customers and Devices."""

from django.contrib import admin
from .models import Customer, Device


class DeviceInline(admin.TabularInline):
    model = Device
    extra = 0
    fields = ("category", "brand", "model", "serial_number", "is_active")
    show_change_link = True


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "email", "total_devices", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("name", "phone", "email", "address")
    readonly_fields = ("created_at", "updated_at")
    inlines = [DeviceInline]


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ("brand", "model", "category", "customer", "serial_number", "is_active", "created_at")
    list_filter = ("category", "is_active", "created_at")
    search_fields = ("brand", "model", "serial_number", "customer__name", "customer__phone")
    readonly_fields = ("created_at", "updated_at")
