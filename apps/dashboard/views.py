"""Views for Operational Dashboard, Global Search, and Service Reports."""

import json
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Avg, Count, F, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from apps.accounts.permissions import AdminRequiredMixin
from apps.customers.models import Customer, Device
from apps.tickets.models import CompletionReport, RepairUpdate, ServiceTicket, StatusHistory

User = get_user_model()


class DashboardOverviewView(AdminRequiredMixin, TemplateView):
    """Main Operational Overview Dashboard with real-time shop metrics."""
    template_name = "dashboard/overview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        now = timezone.now()
        start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_of_week = start_of_today - timedelta(days=now.weekday())

        # KPI Counters
        context["total_tickets"] = ServiceTicket.objects.count()
        context["tickets_today"] = ServiceTicket.objects.filter(created_at__gte=start_of_today).count()
        context["tickets_this_week"] = ServiceTicket.objects.filter(created_at__gte=start_of_week).count()

        context["received_count"] = ServiceTicket.objects.filter(status=ServiceTicket.Status.RECEIVED).count()
        context["unassigned_count"] = ServiceTicket.objects.filter(
            assigned_technician__isnull=True
        ).exclude(status__in=[ServiceTicket.Status.DELIVERED, ServiceTicket.Status.CANCELLED]).count()

        context["in_progress_count"] = ServiceTicket.objects.filter(
            status__in=[ServiceTicket.Status.UNDER_DIAGNOSIS, ServiceTicket.Status.IN_PROGRESS]
        ).count()

        context["on_hold_count"] = ServiceTicket.objects.filter(status=ServiceTicket.Status.ON_HOLD).count()
        context["ready_for_delivery_count"] = ServiceTicket.objects.filter(status=ServiceTicket.Status.READY_FOR_DELIVERY).count()
        context["completed_count"] = ServiceTicket.objects.filter(
            status__in=[ServiceTicket.Status.COMPLETED, ServiceTicket.Status.DELIVERED]
        ).count()

        context["urgent_count"] = ServiceTicket.objects.filter(
            priority=ServiceTicket.Priority.URGENT
        ).exclude(status__in=[ServiceTicket.Status.DELIVERED, ServiceTicket.Status.CANCELLED]).count()

        context["total_customers"] = Customer.objects.filter(is_active=True).count()
        context["total_devices"] = Device.objects.filter(is_active=True).count()

        # Status Distribution for Charts
        status_counts = {
            s: ServiceTicket.objects.filter(status=s).count()
            for s in ServiceTicket.Status.values
        }
        context["status_counts_json"] = json.dumps(status_counts)

        # Priority Distribution for Charts
        priority_counts = {
            p: ServiceTicket.objects.filter(priority=p).count()
            for p in ServiceTicket.Priority.values
        }
        context["priority_counts_json"] = json.dumps(priority_counts)

        # Technician Workload Allocation
        technicians = User.objects.filter(is_active=True).annotate(
            active_jobs=Count(
                "assigned_tickets",
                filter=Q(assigned_tickets__status__in=[
                    ServiceTicket.Status.RECEIVED,
                    ServiceTicket.Status.UNDER_DIAGNOSIS,
                    ServiceTicket.Status.IN_PROGRESS,
                    ServiceTicket.Status.ON_HOLD,
                ]),
            ),
            completed_jobs=Count(
                "assigned_tickets",
                filter=Q(assigned_tickets__status__in=[
                    ServiceTicket.Status.COMPLETED,
                    ServiceTicket.Status.READY_FOR_DELIVERY,
                    ServiceTicket.Status.DELIVERED,
                ]),
            ),
        ).filter(Q(role=User.Role.TECHNICIAN) | Q(active_jobs__gt=0)).order_by("-active_jobs")
        context["technician_workload"] = technicians

        # Recent Activity Feeds
        context["recent_tickets"] = ServiceTicket.objects.select_related("customer", "device").order_by("-created_at")[:5]
        context["recent_updates"] = RepairUpdate.objects.select_related("ticket", "author").order_by("-created_at")[:5]
        context["recent_status_changes"] = StatusHistory.objects.select_related("ticket", "changed_by").order_by("-changed_at")[:5]

        return context


class GlobalSearchView(AdminRequiredMixin, View):
    """Unified search matching across Tickets, Customers, and Equipment (Admin only)."""
    template_name = "dashboard/global_search.html"

    def get(self, request, *args, **kwargs):
        query = request.GET.get("q", "").strip()
        if not query:
            return render(request, self.template_name, {"query": "", "results_found": False})

        # Check for direct exact match on ticket number
        exact_ticket = ServiceTicket.objects.filter(ticket_number__iexact=query).first()
        if exact_ticket:
            return redirect(exact_ticket.get_absolute_url())

        # Match tickets
        tickets = ServiceTicket.objects.select_related("customer", "device", "assigned_technician").filter(
            Q(ticket_number__icontains=query)
            | Q(issue_description__icontains=query)
            | Q(device__serial_number__icontains=query)
            | Q(device__brand__icontains=query)
            | Q(device__model__icontains=query)
        )[:10]

        # Match customers
        customers = Customer.objects.prefetch_related("devices").filter(
            Q(name__icontains=query)
            | Q(phone__icontains=query)
            | Q(email__icontains=query)
            | Q(address__icontains=query)
        )[:10]

        # Match devices
        devices = Device.objects.select_related("customer").filter(
            Q(serial_number__icontains=query)
            | Q(brand__icontains=query)
            | Q(model__icontains=query)
            | Q(customer__name__icontains=query)
            | Q(customer__phone__icontains=query)
        )[:10]

        total_matches = tickets.count() + customers.count() + devices.count()

        return render(
            request,
            self.template_name,
            {
                "query": query,
                "tickets": tickets,
                "customers": customers,
                "devices": devices,
                "total_matches": total_matches,
                "results_found": total_matches > 0,
            },
        )


class ReportsView(AdminRequiredMixin, TemplateView):
    """Operational Reports view with date filters and productivity analytics."""
    template_name = "dashboard/reports.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        time_range = self.request.GET.get("range", "30d")
        now = timezone.now()

        if time_range == "7d":
            start_date = now - timedelta(days=7)
            range_label = "Last 7 Days"
        elif time_range == "90d":
            start_date = now - timedelta(days=90)
            range_label = "Last 90 Days"
        elif time_range == "all":
            start_date = None
            range_label = "All Time"
        else:
            start_date = now - timedelta(days=30)
            range_label = "Last 30 Days"

        tickets_qs = ServiceTicket.objects.all()
        if start_date:
            tickets_qs = tickets_qs.filter(created_at__gte=start_date)

        context["range"] = time_range
        context["range_label"] = range_label
        context["total_in_period"] = tickets_qs.count()
        context["completed_in_period"] = tickets_qs.filter(
            status__in=[ServiceTicket.Status.COMPLETED, ServiceTicket.Status.READY_FOR_DELIVERY, ServiceTicket.Status.DELIVERED]
        ).count()

        # Category Breakdown
        categories_data = (
            tickets_qs.values("device__category")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        context["categories_breakdown"] = categories_data

        # Status Breakdown
        status_data = (
            tickets_qs.values("status")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        context["status_breakdown"] = status_data

        # Priority Breakdown
        priority_data = (
            tickets_qs.values("priority")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        context["priority_breakdown"] = priority_data

        # Technician Productivity in period
        tech_qs = User.objects.filter(is_active=True).annotate(
            assigned_count=Count(
                "assigned_tickets",
                filter=Q(assigned_tickets__created_at__gte=start_date) if start_date else Q(),
            ),
            completed_count=Count(
                "assigned_tickets",
                filter=(
                    Q(assigned_tickets__created_at__gte=start_date, assigned_tickets__status__in=[ServiceTicket.Status.COMPLETED, ServiceTicket.Status.DELIVERED])
                    if start_date
                    else Q(assigned_tickets__status__in=[ServiceTicket.Status.COMPLETED, ServiceTicket.Status.DELIVERED])
                ),
            ),
        ).filter(Q(role=User.Role.TECHNICIAN) | Q(assigned_count__gt=0)).order_by("-completed_count")
        context["technician_stats"] = tech_qs

        return context
