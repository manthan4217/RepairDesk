"""Automated tests verifying Role-Based Access Control (RBAC) UI and Navigation Visibility (Batch 3)."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.customers.models import Customer, Device
from apps.tickets.models import ServiceTicket

User = get_user_model()


class RBACNavigationAndUIVisibilityTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin_ui",
            password="testpassword",
            role=User.Role.ADMINISTRATOR,
            display_name="Boss Admin",
        )
        self.tech = User.objects.create_user(
            username="tech_ui",
            password="testpassword",
            role=User.Role.TECHNICIAN,
            display_name="Field Tech",
        )
        self.customer = Customer.objects.create(
            name="Apex Technologies",
            phone="9988112233",
            email="support@apex.com",
            address="Building 4, Sector 5",
        )
        self.device = Device.objects.create(
            customer=self.customer,
            category=Device.Category.LAPTOP,
            brand="Dell",
            model="XPS 13 Plus",
            serial_number="DELL-XPS-UI-01",
            customer_reported_issue="Battery replacement required",
        )
        self.ticket = ServiceTicket.objects.create(
            customer=self.customer,
            device=self.device,
            created_by=self.admin,
            assigned_technician=self.tech,
            priority=ServiceTicket.Priority.HIGH,
            status=ServiceTicket.Status.IN_PROGRESS,
            issue_description="Replace 55Wh battery pack",
        )

    def test_admin_navigation_bar_shows_all_management_links_and_search(self):
        self.client.login(username="admin_ui", password="testpassword")
        response = self.client.get(reverse("dashboard:overview"))
        self.assertEqual(response.status_code, 200)

        # Admin nav elements
        self.assertContains(response, 'href="/dashboard/"')
        self.assertContains(response, 'href="/tickets/"')
        self.assertContains(response, 'href="/tickets/my-jobs/"')
        self.assertContains(response, 'href="/customers/"')
        self.assertContains(response, 'href="/customers/devices/"')
        self.assertContains(response, 'href="/dashboard/reports/"')
        self.assertContains(response, 'href="/admin/"')
        # Admin global search bar form
        self.assertContains(response, 'action="/dashboard/search/"')

    def test_technician_navigation_bar_hides_admin_links_and_search(self):
        self.client.login(username="tech_ui", password="testpassword")
        response = self.client.get(reverse("tickets:my_jobs"))
        self.assertEqual(response.status_code, 200)

        # Technician sees My Jobs
        self.assertContains(response, 'href="/tickets/my-jobs/"')

        # Technician does NOT see admin management nav items
        self.assertNotContains(response, 'href="/dashboard/"')
        self.assertNotContains(response, 'href="/customers/"')
        self.assertNotContains(response, 'href="/customers/devices/"')
        self.assertNotContains(response, 'href="/dashboard/reports/"')
        self.assertNotContains(response, 'href="/admin/"')
        # Technician does NOT see the global search bar
        self.assertNotContains(response, 'action="/dashboard/search/"')

    def test_admin_ticket_detail_ui_shows_management_controls(self):
        self.client.login(username="admin_ui", password="testpassword")
        response = self.client.get(self.ticket.get_absolute_url())
        self.assertEqual(response.status_code, 200)

        # Admin controls visible
        self.assertContains(response, reverse("tickets:ticket_assign", kwargs={"pk": self.ticket.pk}))
        self.assertContains(response, reverse("tickets:ticket_update", kwargs={"pk": self.ticket.pk}))
        self.assertContains(response, "View Device Record")
        self.assertContains(response, "View Customer Profile")
        self.assertContains(response, self.device.get_absolute_url())
        self.assertContains(response, self.customer.get_absolute_url())

    def test_technician_ticket_detail_ui_hides_management_controls(self):
        self.client.login(username="tech_ui", password="testpassword")
        response = self.client.get(self.ticket.get_absolute_url())
        self.assertEqual(response.status_code, 200)

        # Technician does NOT see admin buttons
        self.assertNotContains(response, reverse("tickets:ticket_assign", kwargs={"pk": self.ticket.pk}))
        self.assertNotContains(response, reverse("tickets:ticket_update", kwargs={"pk": self.ticket.pk}))
        self.assertNotContains(response, "View Device Record")
        self.assertNotContains(response, "View Customer Profile")
        # Technician does NOT get links to global customer/device detail views
        self.assertNotContains(response, f'href="{self.device.get_absolute_url()}"')
        self.assertNotContains(response, f'href="{self.customer.get_absolute_url()}"')

        # Technician DOES see technician action buttons
        self.assertContains(response, reverse("tickets:repair_update_create", kwargs={"pk": self.ticket.pk}))
        self.assertContains(response, reverse("tickets:ticket_status_update", kwargs={"pk": self.ticket.pk}))
        self.assertContains(response, reverse("tickets:completion_report_create", kwargs={"pk": self.ticket.pk}))

    def test_ticket_list_ui_controls(self):
        # Admin sees "+ New Service Ticket" and "Edit"
        self.client.login(username="admin_ui", password="testpassword")
        response_admin = self.client.get(reverse("tickets:ticket_list"))
        self.assertContains(response_admin, "+ New Service Ticket")
        self.assertContains(response_admin, reverse("tickets:ticket_update", kwargs={"pk": self.ticket.pk}))

        # Technician does NOT see "+ New Service Ticket" or "Edit"
        self.client.login(username="tech_ui", password="testpassword")
        response_tech = self.client.get(reverse("tickets:ticket_list"))
        self.assertNotContains(response_tech, "+ New Service Ticket")
        self.assertNotContains(response_tech, reverse("tickets:ticket_update", kwargs={"pk": self.ticket.pk}))
