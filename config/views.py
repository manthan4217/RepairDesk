"""Project-level pages that do not belong to one business app."""

from django.shortcuts import redirect, render


def home(request):
    if request.user.is_authenticated:
        return redirect("dashboard:overview")
    return render(request, "home.html")

