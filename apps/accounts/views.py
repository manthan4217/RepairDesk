"""Authentication and profile views for RepairDesk."""

from django.contrib import messages
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import FormView

from .forms import LoginForm, UserProfileForm


class UserLoginView(DjangoLoginView):
    """Custom login view using Bootstrap-styled LoginForm and redirect logic."""
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_success_url(self):
        redirect_to = self.request.GET.get("next") or self.request.POST.get("next")
        if redirect_to and url_has_allowed_host_and_scheme(
            url=redirect_to,
            allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        ):
            return redirect_to

        user = self.request.user
        if user.is_authenticated:
            messages.success(self.request, f"Welcome back, {user.display_name or user.username}!")
            return reverse_lazy("home")
        return reverse_lazy("home")


class UserLogoutView(View):
    """Logs out the active user and redirects home with a message. Strictly POST-only to prevent CSRF logout."""
    def post(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            auth_logout(request)
            messages.info(request, "You have been signed out.")
        return redirect("home")


class ProfileView(LoginRequiredMixin, FormView):
    """Allows authenticated staff members to inspect and update their details."""
    template_name = "accounts/profile.html"
    form_class = UserProfileForm
    success_url = reverse_lazy("accounts:profile")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Your profile has been updated successfully.")
        return super().form_valid(form)
