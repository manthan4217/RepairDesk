"""Forms for user authentication and profile management."""

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import User


class LoginForm(AuthenticationForm):
    """Authentication form styled with Bootstrap 5."""
    username = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter your username",
                "autofocus": True,
            }
        )
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter your password",
            }
        )
    )


class UserProfileForm(forms.ModelForm):
    """Form allowing staff members to update their profile details."""
    class Meta:
        model = User
        fields = ["display_name", "email", "phone"]
        widgets = {
            "display_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control", "placeholder": "+91 98765 43210"}),
        }
