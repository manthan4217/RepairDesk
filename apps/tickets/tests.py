"""Automated tests for Service Tickets and Assignment Engine (Phase 3)."""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.customers.models import Customer, Device
from .forms import TicketCreateForm
from .models import Assignment, ServiceTicket
from .services import generate_ticket_number

User = get_user_model()


class TicketModelAndSequenceTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="intake_agent",
            password="testpassword",
            role=User.Role.ADMINISTRATOR,
        )
        self.tech_user = User.objects.create_user(
            username="repair_tech",
            password="testpassword",
            role=User.Role.TECHNICIAN,
        )
        self.customer1 = Customer.objects.create(name="Customer 1", phone="1111111111")
        self.customer2 = Customer.objects.create(name="Customer 2", phone="2222222222")

        self.device1 = Device.objects.create(
            customer=self.customer1,
            category=Device.Category.LAPTOP,
            brand="Dell",
            model="XPS 13",
            serial_number="XPS-001",
            customer_reported_issue="No display",
        )
        self.device2 = Device.objects.create(
            customer=self.customer2,
            category=Device.Category.SMARTPHONE,
            brand="Apple",
            model="iPhone 14",
            customer_reported_issue="Broken back glass",
        )

    def test_ticket_number_generation_format(self):
        num1 = generate_ticket_number()
        self.assertTrue(num1.startswith("RD-"))
        self.assertTrue(num1.endswith("00001"))

        # Create ticket with num1
        ServiceTicket.objects.create(
            customer=self.customer1,
            device=self.device1,
            created_by=self.staff_user,
            issue_description="Screen replacement needed",
        )

        num2 = generate_ticket_number()
        self.assertTrue(num2.endswith("00002"))

    def test_device_must_belong_to_customer_validation(self):
        """A ticket with Customer 1 and Device 2 (belonging to Customer 2) must fail validation."""
        ticket = ServiceTicket(
            customer=self.customer1,
            device=self.device2,  # Owned by customer2!
            created_by=self.staff_user,
            issue_description="Mismatched ownership test",
        )
        with self.assertRaises(ValidationError):
            ticket.full_clean()

    def test_assign_to_workflow(self):
        ticket = ServiceTicket.objects.create(
            customer=self.customer1,
            device=self.device1,
            created_by=self.staff_user,
            issue_description="Diagnostic inspection",
        )
        self.assertIsNone(ticket.assigned_technician)
        self.assertEqual(ticket.assignments.count(), 0)

        # Assign to repair_tech
        ticket.assign_to(
            technician=self.tech_user,
            assigned_by=self.staff_user,
            notes="Please expedite this ticket",
        )

        ticket.refresh_from_db()
        self.assertEqual(ticket.assigned_technician, self.tech_user)
        self.assertEqual(ticket.assignments.count(), 1)

        assignment = ticket.assignments.first()
        self.assertEqual(assignment.technician, self.tech_user)
        self.assertEqual(assignment.assigned_by, self.staff_user)
        self.assertEqual(assignment.notes, "Please expedite this ticket")
        self.assertTrue(assignment.is_current)

    def test_inactive_technician_assignment_rejected(self):
        self.tech_user.is_active = False
        self.tech_user.save()

        ticket = ServiceTicket.objects.create(
            customer=self.customer1,
            device=self.device1,
            created_by=self.staff_user,
            issue_description="Testing inactive assignment",
        )

        with self.assertRaises(ValidationError):
            ticket.assign_to(self.tech_user, self.staff_user)


class TicketViewsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="manager_dan",
            password="testpassword",
            role=User.Role.ADMINISTRATOR,
        )
        self.tech = User.objects.create_user(
            username="tech_bob",
            password="testpassword",
            role=User.Role.TECHNICIAN,
            display_name="Bob Technician",
        )
        self.customer = Customer.objects.create(name="Wayne Enterprises", phone="9988776655")
        self.device = Device.objects.create(
            customer=self.customer,
            category=Device.Category.DESKTOP,
            brand="Custom",
            model="Workstation Pro",
            serial_number="WS-990",
            customer_reported_issue="Overheating under load",
        )
        self.ticket = ServiceTicket.objects.create(
            customer=self.customer,
            device=self.device,
            created_by=self.user,
            priority=ServiceTicket.Priority.HIGH,
            issue_description="CPU throttling after 5 minutes",
            estimated_cost=2500.00,
        )

    def test_ticket_list_view(self):
        self.client.login(username="manager_dan", password="testpassword")
        response = self.client.get(reverse("tickets:ticket_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.ticket.ticket_number)
        self.assertContains(response, "Wayne Enterprises")
        self.assertContains(response, "Workstation Pro")

    def test_ticket_search_and_filter(self):
        self.client.login(username="manager_dan", password="testpassword")
        # Search by ticket number
        response = self.client.get(reverse("tickets:ticket_list"), {"q": self.ticket.ticket_number})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.ticket.ticket_number)

        # Filter by priority
        response_prio = self.client.get(reverse("tickets:ticket_list"), {"priority": "high"})
        self.assertEqual(response_prio.status_code, 200)
        self.assertContains(response_prio, self.ticket.ticket_number)

    def test_ticket_create_view(self):
        self.client.login(username="manager_dan", password="testpassword")
        response = self.client.post(
            reverse("tickets:ticket_create"),
            {
                "customer": self.customer.pk,
                "device": self.device.pk,
                "priority": ServiceTicket.Priority.URGENT,
                "issue_description": "New critical malfunction reported",
                "estimated_cost": "1500.00",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ServiceTicket.objects.count(), 2)
        new_ticket = ServiceTicket.objects.exclude(pk=self.ticket.pk).first()
        self.assertEqual(new_ticket.priority, ServiceTicket.Priority.URGENT)
        self.assertContains(response, new_ticket.ticket_number)

    def test_ticket_detail_view(self):
        self.client.login(username="manager_dan", password="testpassword")
        response = self.client.get(self.ticket.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.ticket.ticket_number)
        self.assertContains(response, "Wayne Enterprises")
        self.assertContains(response, "Workstation Pro")
        self.assertContains(response, "CPU throttling after 5 minutes")

    def test_ticket_assign_view(self):
        self.client.login(username="manager_dan", password="testpassword")
        response = self.client.post(
            reverse("tickets:ticket_assign", kwargs={"pk": self.ticket.pk}),
            {
                "technician": self.tech.pk,
                "notes": "Assigned via web UI",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.assigned_technician, self.tech)
        self.assertContains(response, "Bob Technician")

    def test_customer_devices_json_api(self):
        self.client.login(username="manager_dan", password="testpassword")
        response = self.client.get(
            reverse("tickets:customer_devices_api", kwargs={"customer_id": self.customer.pk})
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("devices", data)
        self.assertEqual(len(data["devices"]), 1)
        self.assertEqual(data["devices"][0]["id"], self.device.pk)
        self.assertIn("Workstation Pro", data["devices"][0]["label"])
