"""Views for Customer management and Device registration."""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.accounts.permissions import AdminRequiredMixin
from .forms import CustomerForm, CustomerSearchForm, DeviceForm, DeviceSearchForm
from .models import Customer, Device


class CustomerListView(LoginRequiredMixin, ListView):
    """Searchable, paginated list of customers."""
    model = Customer
    template_name = "customers/customer_list.html"
    context_object_name = "customers"
    paginate_by = 10

    def get_queryset(self):
        queryset = Customer.objects.prefetch_related("devices").all()
        q = self.request.GET.get("q", "").strip()
        status = self.request.GET.get("status", "").strip()

        if q:
            queryset = queryset.filter(
                Q(name__icontains=q) | Q(phone__icontains=q) | Q(email__icontains=q)
            )

        if status == "active":
            queryset = queryset.filter(is_active=True)
        elif status == "inactive":
            queryset = queryset.filter(is_active=False)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_form"] = CustomerSearchForm(self.request.GET)
        context["total_count"] = Customer.objects.count()
        context["active_count"] = Customer.objects.filter(is_active=True).count()
        return context


class CustomerDetailView(LoginRequiredMixin, DetailView):
    """Detailed view for a customer and their registered equipment."""
    model = Customer
    template_name = "customers/customer_detail.html"
    context_object_name = "customer"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["devices"] = self.object.devices.all()
        return context


class CustomerCreateView(LoginRequiredMixin, CreateView):
    """Register a new customer."""
    model = Customer
    form_class = CustomerForm
    template_name = "customers/customer_form.html"

    def form_valid(self, form):
        messages.success(self.request, f"Customer '{form.instance.name}' registered successfully.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Register New Customer"
        context["submit_label"] = "Save Customer"
        return context


class CustomerUpdateView(LoginRequiredMixin, UpdateView):
    """Update an existing customer's contact information."""
    model = Customer
    form_class = CustomerForm
    template_name = "customers/customer_form.html"

    def form_valid(self, form):
        messages.success(self.request, f"Customer '{form.instance.name}' updated successfully.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Edit Customer: {self.object.name}"
        context["submit_label"] = "Update Customer"
        return context


class CustomerToggleStatusView(LoginRequiredMixin, View):
    """Toggle customer between active and archived status."""
    def post(self, request, pk, *args, **kwargs):
        customer = get_object_or_404(Customer, pk=pk)
        customer.is_active = not customer.is_active
        customer.save(update_fields=["is_active", "updated_at"])
        status_label = "activated" if customer.is_active else "archived"
        messages.info(request, f"Customer '{customer.name}' has been {status_label}.")
        return redirect("customers:customer_detail", pk=customer.pk)


class DeviceListView(LoginRequiredMixin, ListView):
    """Searchable, paginated global registry of registered devices."""
    model = Device
    template_name = "customers/device_list.html"
    context_object_name = "devices"
    paginate_by = 10

    def get_queryset(self):
        queryset = Device.objects.select_related("customer").all()
        q = self.request.GET.get("q", "").strip()
        category = self.request.GET.get("category", "").strip()

        if q:
            queryset = queryset.filter(
                Q(brand__icontains=q)
                | Q(model__icontains=q)
                | Q(serial_number__icontains=q)
                | Q(customer__name__icontains=q)
                | Q(customer__phone__icontains=q)
            )

        if category:
            queryset = queryset.filter(category=category)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_form"] = DeviceSearchForm(self.request.GET)
        context["total_devices"] = Device.objects.count()
        return context


class DeviceDetailView(LoginRequiredMixin, DetailView):
    """Detailed view for a single device with intake details and customer info."""
    model = Device
    template_name = "customers/device_detail.html"
    context_object_name = "device"


class DeviceCreateView(LoginRequiredMixin, CreateView):
    """Register a new device, optionally attached to a specific customer."""
    model = Device
    form_class = DeviceForm
    template_name = "customers/device_form.html"

    def get_initial(self):
        initial = super().get_initial()
        customer_id = self.request.GET.get("customer")
        if customer_id:
            customer = get_object_or_404(Customer, pk=customer_id)
            initial["customer"] = customer
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        customer_id = self.request.GET.get("customer")
        if customer_id:
            kwargs["customer"] = get_object_or_404(Customer, pk=customer_id)
        return kwargs

    def form_valid(self, form):
        device = form.save()
        messages.success(
            self.request,
            f"Device '{device.brand} {device.model}' registered for {device.customer.name}.",
        )
        return redirect("customers:device_detail", pk=device.pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customer_id = self.request.GET.get("customer")
        if customer_id:
            context["customer"] = get_object_or_404(Customer, pk=customer_id)
        context["page_title"] = "Register Device / Equipment"
        context["submit_label"] = "Register Device"
        return context


class DeviceUpdateView(LoginRequiredMixin, UpdateView):
    """Update details of an existing device."""
    model = Device
    form_class = DeviceForm
    template_name = "customers/device_form.html"

    def form_valid(self, form):
        device = form.save()
        messages.success(self.request, f"Device '{device.brand} {device.model}' updated.")
        return redirect("customers:device_detail", pk=device.pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["customer"] = self.object.customer
        context["page_title"] = f"Edit Device: {self.object.brand} {self.object.model}"
        context["submit_label"] = "Update Device"
        return context
