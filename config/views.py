"""Project-level pages that do not belong to one business app."""

from django.shortcuts import render


def home(request):
    return render(request, "home.html")
