"""Views for Service Ticket lifecycle, intake, technician assignments, repair notes, and completion reports."""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, DetailView, FormView, ListView, UpdateView

from apps.customers.models import Customer, Device
from .forms import (
    CompletionReportForm,
    RepairUpdateForm,
    StatusTransitionForm,
    TicketAssignForm,
    TicketCreateForm,
    TicketFilterForm,
    TicketUpdateForm,
)
from .models import CompletionReport, RepairUpdate, ServiceTicket


def check_ticket_access(ticket, user):
    """Ensures user is an administrator or the currently assigned technician."""
    if not (user.is_administrator or ticket.assigned_technician == user):
        raise PermissionDenied("You do not have permission to modify this ticket or submit repair reports.")


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


class MyJobsListView(LoginRequiredMixin, ListView):
    """Technician Workspace: lists tickets assigned exclusively to the logged-in staff member."""
    model = ServiceTicket
    template_name = "tickets/my_jobs.html"
    context_object_name = "tickets"
    paginate_by = 10

    def get_queryset(self):
        return (
            ServiceTicket.objects.filter(assigned_technician=self.request.user)
            .select_related("customer", "device")
            .order_by("-updated_at")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_tickets = ServiceTicket.objects.filter(assigned_technician=self.request.user)
        context["my_total"] = user_tickets.count()
        context["my_in_progress"] = user_tickets.filter(
            status__in=[ServiceTicket.Status.UNDER_DIAGNOSIS, ServiceTicket.Status.IN_PROGRESS]
        ).count()
        context["my_completed"] = user_tickets.filter(
            status__in=[ServiceTicket.Status.COMPLETED, ServiceTicket.Status.READY_FOR_DELIVERY]
        ).count()
        return context


class TicketDetailView(LoginRequiredMixin, DetailView):
    """Detailed view of a Service Ticket, including assignment history, repair notes, and completion report."""
    model = ServiceTicket
    template_name = "tickets/ticket_detail.html"
    context_object_name = "ticket"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ticket = self.object
        context["assignments"] = ticket.assignments.select_related("technician", "assigned_by").all()
        context["updates"] = ticket.updates.select_related("author").all()
        context["status_history"] = ticket.status_history.select_related("changed_by").all()
        context["assign_form"] = TicketAssignForm()
        context["can_modify"] = (
            self.request.user.is_administrator or ticket.assigned_technician == self.request.user
        )
        context["has_completion_report"] = hasattr(ticket, "completion_report")
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


class RepairUpdateCreateView(LoginRequiredMixin, CreateView):
    """Add a diagnosis finding or repair progress note to a ticket."""
    model = RepairUpdate
    form_class = RepairUpdateForm
    template_name = "tickets/repair_update_form.html"

    def get_ticket(self):
        return get_object_or_404(ServiceTicket, pk=self.kwargs["pk"])

    def dispatch(self, request, *args, **kwargs):
        ticket = self.get_ticket()
        check_ticket_access(ticket, request.user)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        ticket = self.get_ticket()
        form.instance.ticket = ticket
        form.instance.author = self.request.user
        form.save()
        messages.success(self.request, "Repair note added successfully.")
        return redirect(ticket.get_absolute_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["ticket"] = self.get_ticket()
        return context


class TicketStatusTransitionView(LoginRequiredMixin, FormView):
    """Update ticket workflow status and audit trail."""
    form_class = StatusTransitionForm
    template_name = "tickets/status_form.html"

    def get_ticket(self):
        return get_object_or_404(ServiceTicket, pk=self.kwargs["pk"])

    def dispatch(self, request, *args, **kwargs):
        ticket = self.get_ticket()
        check_ticket_access(ticket, request.user)
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["ticket"] = self.get_ticket()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        ticket = self.get_ticket()
        new_status = form.cleaned_data["status"]
        reason = form.cleaned_data.get("reason", "")

        try:
            ticket.update_status(new_status=new_status, user=self.request.user, reason=reason)
            messages.success(self.request, f"Status updated to '{ticket.get_status_display()}'.")
        except ValidationError as e:
            form.add_error(None, e.message)
            return self.form_invalid(form)

        return redirect(ticket.get_absolute_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["ticket"] = self.get_ticket()
        return context


class CompletionReportCreateView(LoginRequiredMixin, CreateView):
    """Submit formal completion report concluding repair work."""
    model = CompletionReport
    form_class = CompletionReportForm
    template_name = "tickets/completion_report_form.html"

    def get_ticket(self):
        return get_object_or_404(ServiceTicket, pk=self.kwargs["pk"])

    def dispatch(self, request, *args, **kwargs):
        ticket = self.get_ticket()
        check_ticket_access(ticket, request.user)
        if hasattr(ticket, "completion_report"):
            messages.info(request, "This ticket already has a completion report.")
            return redirect(ticket.get_absolute_url())
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        ticket = self.get_ticket()
        form.instance.ticket = ticket
        form.instance.technician = self.request.user
        form.save()

        # Concurrently transition status to COMPLETED
        try:
            ticket.update_status(
                new_status=ServiceTicket.Status.COMPLETED,
                user=self.request.user,
                reason="Repair completed and completion report submitted.",
            )
        except ValidationError:
            old_status = ticket.status
            ticket.status = ServiceTicket.Status.COMPLETED
            ticket.save(update_fields=["status", "updated_at"])
            from .models import StatusHistory
            StatusHistory.objects.create(
                ticket=ticket,
                old_status=old_status,
                new_status=ServiceTicket.Status.COMPLETED,
                changed_by=self.request.user,
                reason="Completion report submitted and signed.",
            )

        messages.success(self.request, f"Completion report for {ticket.ticket_number} submitted successfully.")
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
