"""Services for Service Ticket creation, numbers, and business operations."""

from django.db import transaction
from django.utils import timezone


def generate_ticket_number():
    """Generates a collision-safe, sequential human-readable ticket number.
    Format: RD-YYYY-XXXXX (e.g., RD-2026-00001)
    """
    from .models import ServiceTicket

    year = timezone.now().year
    prefix = f"RD-{year}-"

    with transaction.atomic():
        last_ticket = (
            ServiceTicket.objects.select_for_update()
            .filter(ticket_number__startswith=prefix)
            .order_by("-ticket_number")
            .first()
        )
        if last_ticket:
            try:
                last_seq = int(last_ticket.ticket_number.split("-")[-1])
                new_seq = last_seq + 1
            except (ValueError, IndexError):
                new_seq = ServiceTicket.objects.filter(ticket_number__startswith=prefix).count() + 1
        else:
            new_seq = 1

        candidate = f"{prefix}{new_seq:05d}"
        while ServiceTicket.objects.filter(ticket_number=candidate).exists():
            new_seq += 1
            candidate = f"{prefix}{new_seq:05d}"

        return candidate
