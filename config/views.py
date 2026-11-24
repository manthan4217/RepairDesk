"""Project-level pages that do not belong to one business app."""

from django.shortcuts import redirect, render


def home(request):
    if request.user.is_authenticated:
        if request.user.is_administrator:
            return redirect("dashboard:overview")
        return redirect("tickets:my_jobs")
    return render(request, "home.html")

