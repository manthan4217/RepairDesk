from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("RepairDesk", {"fields": ("role", "phone", "display_name")}),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ("RepairDesk", {"fields": ("role", "phone", "display_name")}),
    )
    list_display = (
        "username",
        "email",
        "display_name",
        "role",
        "is_staff",
        "is_active",
    )
    list_filter = ("role", "is_staff", "is_active")
    search_fields = ("username", "email", "display_name", "phone")
