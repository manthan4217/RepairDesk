"""Views for Service Ticket lifecycle, intake, and technician assignment."""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, DetailView, FormView, ListView, UpdateView

from apps.customers.models import Customer, Device
from .forms import TicketAssignForm, TicketCreateForm, TicketFilterForm, TicketUpdateForm
from .models import ServiceTicket


class TicketListView(LoginRequiredMixin, ListView):
    """Filterable, paginated dashboard list of all service tickets."""
    model = ServiceTicket
    template_name = "tickets/ticket_list.html"
    context_object_name = "tickets"
    paginate_by = 10

    def get_queryset(self):
        queryset = (
            ServiceTicket.objects.select_related("customer", "device", "assigned_technician")
            .all()
        )
        q = self.request.GET.get("q", "").strip()
        status = self.request.GET.get("status", "").strip()
        priority = self.request.GET.get("priority", "").strip()
        assignment = self.request.GET.get("assignment", "").strip()

        if q:
            queryset = queryset.filter(
                Q(ticket_number__icontains=q)
                | Q(customer__name__icontains=q)
                | Q(customer__phone__icontains=q)
                | Q(device__brand__icontains=q)
                | Q(device__model__icontains=q)
                | Q(device__serial_number__icontains=q)
            )

        if status:
            queryset = queryset.filter(status=status)

        if priority:
            queryset = queryset.filter(priority=priority)

        if assignment == "unassigned":
            queryset = queryset.filter(assigned_technician__isnull=True)
        elif assignment == "assigned":
            queryset = queryset.filter(assigned_technician__isnull=False)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_form"] = TicketFilterForm(self.request.GET)
        context["total_tickets"] = ServiceTicket.objects.count()
        context["in_progress_count"] = ServiceTicket.objects.filter(
            status__in=[ServiceTicket.Status.RECEIVED, ServiceTicket.Status.UNDER_DIAGNOSIS, ServiceTicket.Status.IN_PROGRESS]
        ).count()
        context["completed_count"] = ServiceTicket.objects.filter(
            status__in=[ServiceTicket.Status.COMPLETED, ServiceTicket.Status.READY_FOR_DELIVERY, ServiceTicket.Status.DELIVERED]
        ).count()
        context["unassigned_count"] = ServiceTicket.objects.filter(assigned_technician__isnull=True).count()
        return context


class TicketDetailView(LoginRequiredMixin, DetailView):
    """Detailed view of a Service Ticket, including assignment history and timeline."""
    model = ServiceTicket
    template_name = "tickets/ticket_detail.html"
    context_object_name = "ticket"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["assignments"] = self.object.assignments.select_related("technician", "assigned_by").all()
        context["assign_form"] = TicketAssignForm()
        return context


class TicketCreateView(LoginRequiredMixin, CreateView):
    """Intake wizard to create a new service ticket."""
    model = ServiceTicket
    form_class = TicketCreateForm
    template_name = "tickets/ticket_form.html"

    def get_initial(self):
        initial = super().get_initial()
        customer_id = self.request.GET.get("customer")
        device_id = self.request.GET.get("device")

        if customer_id:
            try:
                initial["customer"] = Customer.objects.get(pk=customer_id)
            except Customer.DoesNotExist:
                pass

        if device_id:
            try:
                device = Device.objects.get(pk=device_id)
                initial["device"] = device
                if not customer_id:
                    initial["customer"] = device.customer
            except Device.DoesNotExist:
                pass

        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        customer_id = self.request.GET.get("customer")
        device_id = self.request.GET.get("device")

        if customer_id:
            try:
                kwargs["customer"] = Customer.objects.get(pk=customer_id)
            except Customer.DoesNotExist:
                pass

        if device_id:
            try:
                kwargs["device"] = Device.objects.get(pk=device_id)
            except Device.DoesNotExist:
                pass

        return kwargs

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        ticket = form.save()
        messages.success(self.request, f"Service Ticket {ticket.ticket_number} created successfully.")
        return redirect(ticket.get_absolute_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Create Service Ticket"
        context["submit_label"] = "Generate Ticket"
        return context


class TicketUpdateView(LoginRequiredMixin, UpdateView):
    """Edit ticket metadata, priority, status or estimated cost."""
    model = ServiceTicket
    form_class = TicketUpdateForm
    template_name = "tickets/ticket_form.html"

    def form_valid(self, form):
        ticket = form.save()
        messages.success(self.request, f"Ticket {ticket.ticket_number} updated.")
        return redirect(ticket.get_absolute_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Edit Ticket: {self.object.ticket_number}"
        context["submit_label"] = "Save Changes"
        return context


class TicketAssignView(LoginRequiredMixin, FormView):
    """Assign or reassign a ticket to an active technician."""
    form_class = TicketAssignForm
    template_name = "tickets/ticket_assign.html"

    def get_ticket(self):
        return get_object_or_404(ServiceTicket, pk=self.kwargs["pk"])

    def form_valid(self, form):
        ticket = self.get_ticket()
        technician = form.cleaned_data["technician"]
        notes = form.cleaned_data.get("notes", "")

        ticket.assign_to(
            technician=technician,
            assigned_by=self.request.user,
            notes=notes,
        )

        messages.success(
            self.request,
            f"Ticket {ticket.ticket_number} assigned to {technician.display_name or technician.username}.",
        )
        return redirect(ticket.get_absolute_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["ticket"] = self.get_ticket()
        return context


def customer_devices_json(request, customer_id):
    """Lightweight endpoint returning active devices belonging to a customer."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    devices = Device.objects.filter(customer_id=customer_id, is_active=True).values(
        "id", "brand", "model", "serial_number"
    )
    device_list = [
        {
            "id": d["id"],
            "label": f"{d['brand']} {d['model']}" + (f" (SN: {d['serial_number']})" if d["serial_number"] else ""),
        }
        for d in devices
    ]
    return JsonResponse({"devices": device_list})
