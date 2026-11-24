"""Role-based access permissions and mixins for RepairDesk."""

from functools import wraps
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


def admin_required(view_func):
    """View decorator restricting access to authenticated administrators."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"/accounts/login/?next={request.path}")
        if not request.user.is_administrator:
            raise PermissionDenied("You do not have administrative privileges to access this page.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def technician_required(view_func):
    """View decorator restricting access to authenticated technicians (or administrators)."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"/accounts/login/?next={request.path}")
        if not (request.user.is_technician or request.user.is_administrator):
            raise PermissionDenied("You must be a technician or administrator to access this page.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


class AdminRequiredMixin(UserPassesTestMixin):
    """Class-based view mixin restricting access to administrators."""
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_administrator

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        raise PermissionDenied("You do not have administrative privileges to access this page.")


class TechnicianRequiredMixin(UserPassesTestMixin):
    """Class-based view mixin restricting access to technicians (or administrators)."""
    def test_func(self):
        return (
            self.request.user.is_authenticated
            and (self.request.user.is_technician or self.request.user.is_administrator)
        )

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        raise PermissionDenied("You do not have permission to access technician views.")
