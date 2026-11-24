"""Automated tests for Dashboard, Global Search, and Operational Reports (Phase 5)."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.customers.models import Customer, Device
from apps.tickets.models import CompletionReport, ServiceTicket

User = get_user_model()


class DashboardOverviewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin_dash",
            password="testpassword",
            role=User.Role.ADMINISTRATOR,
            display_name="Boss Admin",
        )
        self.tech = User.objects.create_user(
            username="tech_dan",
            password="testpassword",
            role=User.Role.TECHNICIAN,
            display_name="Dan Tech",
        )
        self.customer = Customer.objects.create(name="Cyberdyne Systems", phone="9998887777")
        self.device = Device.objects.create(
            customer=self.customer,
            category=Device.Category.LAPTOP,
            brand="Dell",
            model="Latitude 7420",
            serial_number="LAT-7420-1",
            customer_reported_issue="Cracked display",
        )
        self.ticket = ServiceTicket.objects.create(
            customer=self.customer,
            device=self.device,
            created_by=self.admin,
            assigned_technician=self.tech,
            status=ServiceTicket.Status.IN_PROGRESS,
            priority=ServiceTicket.Priority.HIGH,
            issue_description="Replace LCD panel",
        )

    def test_unauthenticated_user_redirected(self):
        response = self.client.get(reverse("dashboard:overview"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_dashboard_renders_live_counters(self):
        self.client.login(username="admin_dash", password="testpassword")
        response = self.client.get(reverse("dashboard:overview"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Operational Dashboard")
        self.assertContains(response, "Dan Tech")
        self.assertContains(response, self.ticket.ticket_number)

        # Context assertions
        context = response.context
        self.assertEqual(context["total_tickets"], 1)
        self.assertEqual(context["in_progress_count"], 1)
        self.assertEqual(context["unassigned_count"], 0)


class GlobalSearchTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="search_user",
            password="testpassword",
            role=User.Role.ADMINISTRATOR,
        )
        self.customer = Customer.objects.create(
            name="Stark Industries",
            phone="9876543219",
            email="tony@stark.com",
        )
        self.device = Device.objects.create(
            customer=self.customer,
            category=Device.Category.DESKTOP,
            brand="StarkTech",
            model="Arc Server",
            serial_number="ARC-REACTOR-3000",
            customer_reported_issue="Cooling system failure",
        )
        self.ticket = ServiceTicket.objects.create(
            customer=self.customer,
            device=self.device,
            created_by=self.user,
            issue_description="Replace coolant lines",
        )

    def test_exact_ticket_number_redirects_to_detail(self):
        self.client.login(username="search_user", password="testpassword")
        response = self.client.get(reverse("dashboard:search"), {"q": self.ticket.ticket_number})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.ticket.get_absolute_url())

    def test_partial_search_matches_customer_and_device(self):
        self.client.login(username="search_user", password="testpassword")
        response = self.client.get(reverse("dashboard:search"), {"q": "Stark"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Stark Industries")
        self.assertContains(response, "Arc Server")

    def test_search_by_serial_number(self):
        self.client.login(username="search_user", password="testpassword")
        response = self.client.get(reverse("dashboard:search"), {"q": "ARC-REACTOR"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Arc Server")

    def test_search_by_phone(self):
        self.client.login(username="search_user", password="testpassword")
        response = self.client.get(reverse("dashboard:search"), {"q": "9876543219"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Stark Industries")


class ReportsViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="report_admin", password="testpassword", role=User.Role.ADMINISTRATOR)
        self.customer = Customer.objects.create(name="Report Client", phone="9990001111")
        self.device = Device.objects.create(
            customer=self.customer,
            category=Device.Category.SMARTPHONE,
            brand="Google",
            model="Pixel 8",
            customer_reported_issue="Battery replacement",
        )
        self.ticket = ServiceTicket.objects.create(
            customer=self.customer,
            device=self.device,
            created_by=self.admin,
            assigned_technician=self.admin,
            status=ServiceTicket.Status.COMPLETED,
            issue_description="Battery replaced",
        )

    def test_reports_view_renders_breakdown(self):
        self.client.login(username="report_admin", password="testpassword")
        response = self.client.get(reverse("dashboard:reports"), {"range": "30d"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Operational Reports")
        self.assertContains(response, "Equipment Category Breakdown")
        self.assertContains(response, "Technician Productivity Report")

        context = response.context
        self.assertEqual(context["total_in_period"], 1)
        self.assertEqual(context["completed_in_period"], 1)
