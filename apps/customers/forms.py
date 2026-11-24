"""Forms for Customer and Device management."""

import re
from django import forms
from django.core.exceptions import ValidationError
from .models import Customer, Device


class CustomerForm(forms.ModelForm):
    """Form to create or update a Customer record."""

    class Meta:
        model = Customer
        fields = ["name", "phone", "email", "address", "notes", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Full Name or Company"}),
            "phone": forms.TextInput(attrs={"class": "form-control", "placeholder": "+91 98765 43210"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "customer@example.com"}),
            "address": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Street, City, Postal Code"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Internal staff notes (optional)"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean_phone(self):
        phone = self.cleaned_data.get("phone", "").strip()
        # Ensure phone contains digits and sensible length
        digits = re.sub(r"[^\d]", "", phone)
        if len(digits) < 7:
            raise ValidationError("Please provide a valid phone number with at least 7 digits.")
        return phone


class DeviceForm(forms.ModelForm):
    """Form to register or update a Device/Equipment record."""

    class Meta:
        model = Device
        fields = [
            "customer",
            "category",
            "brand",
            "model",
            "serial_number",
            "condition_at_intake",
            "accessories_received",
            "customer_reported_issue",
            "is_active",
        ]
        widgets = {
            "customer": forms.Select(attrs={"class": "form-select"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "brand": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., Apple, Dell, Lenovo, HP"}),
            "model": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., MacBook Pro 16, Latitude 5420"}),
            "serial_number": forms.TextInput(attrs={"class": "form-control", "placeholder": "Serial number, IMEI, or Service Tag"}),
            "condition_at_intake": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Scratches on lid, cracked screen, missing rubber feet..."}),
            "accessories_received": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., Power Adapter 65W, Carry Bag, Mouse"}),
            "customer_reported_issue": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Explain the reported problem in detail..."}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        customer = kwargs.pop("customer", None)
        super().__init__(*args, **kwargs)
        if customer:
            self.fields["customer"].initial = customer
            self.fields["customer"].widget = forms.HiddenInput()


class CustomerSearchForm(forms.Form):
    """Filter and search form for the Customer list."""
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Search by name, phone or email...",
            }
        ),
    )
    status = forms.ChoiceField(
        required=False,
        choices=[
            ("", "All Customers"),
            ("active", "Active Only"),
            ("inactive", "Archived Only"),
        ],
        widget=forms.Select(attrs={"class": "form-select"}),
    )


class DeviceSearchForm(forms.Form):
    """Filter and search form for the Device list."""
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Search by brand, model, serial, or owner...",
            }
        ),
    )
    category = forms.ChoiceField(
        required=False,
        choices=[("", "All Categories")] + list(Device.Category.choices),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
