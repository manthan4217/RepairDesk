"""Forms for Service Ticket creation, editing, assignment, and filtering."""

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from apps.customers.models import Customer, Device
from .models import ServiceTicket

User = get_user_model()


class TicketCreateForm(forms.ModelForm):
    """Intake form to register a new Service Ticket."""

    class Meta:
        model = ServiceTicket
        fields = [
            "customer",
            "device",
            "priority",
            "issue_description",
            "estimated_cost",
        ]
        widgets = {
            "customer": forms.Select(attrs={"class": "form-select", "id": "id_customer"}),
            "device": forms.Select(attrs={"class": "form-select", "id": "id_device"}),
            "priority": forms.Select(attrs={"class": "form-select"}),
            "issue_description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Describe the malfunction, customer symptoms, or specific repair requested...",
                }
            ),
            "estimated_cost": forms.NumberInput(
                attrs={"class": "form-control", "placeholder": "0.00", "step": "0.01"}
            ),
        }

    def __init__(self, *args, **kwargs):
        customer = kwargs.pop("customer", None)
        device = kwargs.pop("device", None)
        super().__init__(*args, **kwargs)

        # Restrict customers to active ones
        self.fields["customer"].queryset = Customer.objects.filter(is_active=True)

        if customer:
            self.fields["customer"].initial = customer
            self.fields["device"].queryset = Device.objects.filter(customer=customer, is_active=True)
        elif self.data.get("customer"):
            try:
                customer_id = int(self.data.get("customer"))
                self.fields["device"].queryset = Device.objects.filter(customer_id=customer_id, is_active=True)
            except (ValueError, TypeError):
                self.fields["device"].queryset = Device.objects.none()
        elif self.instance.pk and self.instance.customer_id:
            self.fields["device"].queryset = Device.objects.filter(customer=self.instance.customer, is_active=True)
        else:
            self.fields["device"].queryset = Device.objects.filter(is_active=True)

        if device:
            self.fields["device"].initial = device

    def clean(self):
        cleaned_data = super().clean()
        customer = cleaned_data.get("customer")
        device = cleaned_data.get("device")

        if customer and device:
            if device.customer != customer:
                raise ValidationError(
                    {"device": f"The device '{device.brand} {device.model}' does not belong to {customer.name}."}
                )
        return cleaned_data


class TicketUpdateForm(forms.ModelForm):
    """Form to update permitted ticket details."""

    class Meta:
        model = ServiceTicket
        fields = ["priority", "status", "issue_description", "estimated_cost"]
        widgets = {
            "priority": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "issue_description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "estimated_cost": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
        }


class TicketAssignForm(forms.Form):
    """Form for assigning or reassigning a ticket to an active technician."""

    technician = forms.ModelChoiceField(
        queryset=User.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        help_text="Select an active technician to take ownership of this repair.",
    )
    notes = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Assignment instructions or priority reason (optional)"}
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only active staff members can be assigned
        self.fields["technician"].queryset = User.objects.filter(is_active=True).order_by("display_name", "username")


class TicketFilterForm(forms.Form):
    """Search and filter form for Service Tickets."""

    q = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Search by ticket #, client, phone, serial or device...",
            }
        ),
    )
    status = forms.ChoiceField(
        required=False,
        choices=[("", "All Statuses")] + list(ServiceTicket.Status.choices),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    priority = forms.ChoiceField(
        required=False,
        choices=[("", "All Priorities")] + list(ServiceTicket.Priority.choices),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    assignment = forms.ChoiceField(
        required=False,
        choices=[
            ("", "All Assignments"),
            ("unassigned", "Unassigned Only"),
            ("assigned", "Assigned Only"),
        ],
        widget=forms.Select(attrs={"class": "form-select"}),
    )
