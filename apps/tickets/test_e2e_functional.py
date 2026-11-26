"""Comprehensive End-to-End Functional Test Suite for RepairDesk (Phase 4).

Covers all 7 functional areas:
1. Authentication & Session Management
2. Customer Management & Validation
3. Device Registry & Ownership Integrity
4. Service Ticket Lifecycle & State Machine Transitions
5. Technician Workspace & Object Authorization
6. Admin Dashboard, KPI Calculations & Global Search
7. UI Rendering, Flash Messages & Custom Error Pages
"""

from decimal import Decimal
import json
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import ProtectedError
from django.test import TestCase, Client
from django.urls import reverse

from apps.customers.models import Customer, Device
from apps.tickets.forms import AttachmentUploadForm, StatusTransitionForm, TicketAssignForm, TicketCreateForm
from apps.tickets.models import Assignment, Attachment, CompletionReport, RepairUpdate, ServiceTicket, StatusHistory

User = get_user_model()


def _close_response_files(response):
    """Safely closes open file handles on streaming responses without firing request_finished."""
    if hasattr(response, "_resource_closers"):
        for closer in response._resource_closers:
            try:
                closer()
            except Exception:
                pass
        response._resource_closers.clear()
        response.closed = True


class EndToEndFunctionalTests(TestCase):
    def setUp(self):
        # 1. Administrator Account
        self.admin = User.objects.create_user(
            username="admin_e2e",
            email="admin_e2e@repairdesk.local",
            password="AdminPassword123!",
            role=User.Role.ADMINISTRATOR,
            display_name="System Admin",
            phone="+91 98765 00001",
            is_staff=True,
            is_superuser=True,
        )

        # 2. Primary Technician
        self.tech1 = User.objects.create_user(
            username="tech_john",
            email="john@repairdesk.local",
            password="TechPassword123!",
            role=User.Role.TECHNICIAN,
            display_name="John Technician",
            phone="+91 98765 00002",
        )

        # 3. Secondary Technician
        self.tech2 = User.objects.create_user(
            username="tech_sarah",
            email="sarah@repairdesk.local",
            password="TechPassword123!",
            role=User.Role.TECHNICIAN,
            display_name="Sarah Specialist",
            phone="+91 98765 00003",
        )

        # 4. Inactive Technician
        self.inactive_tech = User.objects.create_user(
            username="tech_inactive",
            email="inactive@repairdesk.local",
            password="TechPassword123!",
            role=User.Role.TECHNICIAN,
            display_name="Inactive Tech",
            is_active=False,
        )

        # 5. Customers
        self.cust1 = Customer.objects.create(
            name="Alice Walker",
            phone="9876543210",
            email="alice@example.com",
            address="123 Tech Park, Bangalore",
        )
        self.cust2 = Customer.objects.create(
            name="Bob Miller",
            phone="9811223344",
            email="bob@example.com",
            address="456 Silicon Ave, Mumbai",
        )

        # 6. Devices
        self.dev1 = Device.objects.create(
            customer=self.cust1,
            category=Device.Category.LAPTOP,
            brand="Dell",
            model="XPS 15",
            serial_number="DELL-SN-1001",
            customer_reported_issue="Overheating and shutting down",
            accessories_received="Charger 130W",
            condition_at_intake="Light scratches on chassis",
        )
        self.dev2 = Device.objects.create(
            customer=self.cust2,
            category=Device.Category.SMARTPHONE,
            brand="Apple",
            model="iPhone 14 Pro",
            serial_number="APPL-SN-2002",
            customer_reported_issue="Cracked OLED display",
            accessories_received="None",
            condition_at_intake="Cracked glass front",
        )

    # =========================================================================
    # MODULE 1: AUTHENTICATION WORKFLOW
    # =========================================================================

    def test_auth_01_admin_login_and_redirect(self):
        """Admin login succeeds and redirects to dashboard."""
        res = self.client.post(
            reverse("accounts:login"),
            {"username": "admin_e2e", "password": "AdminPassword123!"},
            follow=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.context["user"].is_authenticated)
        self.assertTrue(res.context["user"].is_administrator)
        # Final redirect must be dashboard overview
        self.assertIn(reverse("dashboard:overview"), [r[0] for r in res.redirect_chain])
        self.assertContains(res, "System Admin")

    def test_auth_02_technician_login_and_redirect(self):
        """Technician login succeeds and redirects to my-jobs."""
        res = self.client.post(
            reverse("accounts:login"),
            {"username": "tech_john", "password": "TechPassword123!"},
            follow=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.context["user"].is_authenticated)
        self.assertTrue(res.context["user"].is_technician)
        self.assertIn(reverse("tickets:my_jobs"), [r[0] for r in res.redirect_chain])

    def test_auth_03_invalid_credentials_rejected(self):
        """Invalid password fails authentication with error banner."""
        res = self.client.post(
            reverse("accounts:login"),
            {"username": "admin_e2e", "password": "WrongPassword!"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.context["user"].is_authenticated)
        self.assertContains(res, "Authentication failed:")
        self.assertContains(res, "Please verify your username and password.")

    def test_auth_04_inactive_user_login_blocked(self):
        """Inactive user account cannot authenticate."""
        res = self.client.post(
            reverse("accounts:login"),
            {"username": "tech_inactive", "password": "TechPassword123!"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.context["user"].is_authenticated)
        self.assertContains(res, "Authentication failed:")

    def test_auth_05_post_logout_clears_session(self):
        """POST logout terminates session and redirects home."""
        self.client.login(username="admin_e2e", password="AdminPassword123!")
        res = self.client.post(reverse("accounts:logout"), follow=True)
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.context["user"].is_authenticated)
        self.assertContains(res, "You have been signed out.")

    def test_auth_06_get_logout_method_not_allowed(self):
        """GET logout is rejected with 405 Method Not Allowed."""
        self.client.login(username="admin_e2e", password="AdminPassword123!")
        res = self.client.get(reverse("accounts:logout"))
        self.assertEqual(res.status_code, 405)

    def test_auth_07_profile_update(self):
        """Authenticated user can update profile details."""
        self.client.login(username="tech_john", password="TechPassword123!")
        res = self.client.post(
            reverse("accounts:profile"),
            {
                "display_name": "Johnny Tech Expert",
                "phone": "+91 99999 88888",
                "email": "john.updated@repairdesk.local",
            },
            follow=True,
        )
        self.assertEqual(res.status_code, 200)
        self.tech1.refresh_from_db()
        self.assertEqual(self.tech1.display_name, "Johnny Tech Expert")
        self.assertEqual(self.tech1.phone, "+91 99999 88888")
        self.assertContains(res, "Your profile has been updated successfully.")

    def test_auth_08_home_redirect_by_role(self):
        """Home page '/' properly routes anonymous, admin, and technician users."""
        # Anonymous -> renders public home.html (200)
        res_anon = self.client.get(reverse("home"))
        self.assertEqual(res_anon.status_code, 200)
        self.assertContains(res_anon, "Service and repair management")

        # Admin -> redirects to dashboard:overview
        self.client.login(username="admin_e2e", password="AdminPassword123!")
        res_admin = self.client.get(reverse("home"), follow=True)
        self.assertIn(reverse("dashboard:overview"), [r[0] for r in res_admin.redirect_chain])

        # Technician -> redirects to tickets:my_jobs
        self.client.login(username="tech_john", password="TechPassword123!")
        res_tech = self.client.get(reverse("home"), follow=True)
        self.assertIn(reverse("tickets:my_jobs"), [r[0] for r in res_tech.redirect_chain])

    # =========================================================================
    # MODULE 2: CUSTOMER MANAGEMENT
    # =========================================================================

    def test_cust_01_create_customer_success(self):
        """Admin can register a new customer with complete details."""
        self.client.login(username="admin_e2e", password="AdminPassword123!")
        res = self.client.post(
            reverse("customers:customer_create"),
            {
                "name": "Carlos Santana",
                "phone": "9822334455",
                "email": "carlos@example.com",
                "address": "77 Guitar Lane, Pune",
                "notes": "VIP Client, requires priority turnaround",
            },
            follow=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(Customer.objects.filter(phone="9822334455").exists())
        self.assertContains(res, "Carlos Santana")
        self.assertContains(res, "registered successfully")

    def test_cust_02_invalid_email_fails_validation(self):
        """Invalid customer email triggers form validation error."""
        self.client.login(username="admin_e2e", password="AdminPassword123!")
        res = self.client.post(
            reverse("customers:customer_create"),
            {
                "name": "Invalid Customer",
                "phone": "9800011122",
                "email": "not-an-email",
                "address": "Some Street",
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertFalse(Customer.objects.filter(phone="9800011122").exists())
        self.assertContains(res, "Enter a valid email address.")

    def test_cust_03_customer_detail_and_devices_list(self):
        """Customer detail view lists associated customer devices."""
        self.client.login(username="admin_e2e", password="AdminPassword123!")
        res = self.client.get(reverse("customers:customer_detail", kwargs={"pk": self.cust1.pk}))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Alice Walker")
        self.assertContains(res, "DELL-SN-1001")
        self.assertContains(res, "XPS 15")

    def test_cust_04_search_customers(self):
        """Customer list filter queries match name or phone."""
        self.client.login(username="admin_e2e", password="AdminPassword123!")
        res = self.client.get(reverse("customers:customer_list"), {"q": "Alice"})
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Alice Walker")
        self.assertNotContains(res, "Bob Miller")

    def test_cust_05_update_customer(self):
        """Admin can edit customer contact information."""
        self.client.login(username="admin_e2e", password="AdminPassword123!")
        res = self.client.post(
            reverse("customers:customer_update", kwargs={"pk": self.cust1.pk}),
            {
                "name": "Alice Walker Smith",
                "phone": "9876543210",
                "email": "alice.smith@example.com",
                "address": "New Flat 204, Bangalore",
                "notes": "Updated contact address",
            },
            follow=True,
        )
        self.assertEqual(res.status_code, 200)
        self.cust1.refresh_from_db()
        self.assertEqual(self.cust1.name, "Alice Walker Smith")
        self.assertEqual(self.cust1.email, "alice.smith@example.com")

    def test_cust_06_archive_customer(self):
        """Deactivating customer sets is_active=False."""
        self.client.login(username="admin_e2e", password="AdminPassword123!")
        res = self.client.post(
            reverse("customers:customer_toggle_status", kwargs={"pk": self.cust1.pk}),
            follow=True,
        )
        self.assertEqual(res.status_code, 200)
        self.cust1.refresh_from_db()
        self.assertFalse(self.cust1.is_active)

    def test_cust_07_technician_blocked_from_customers(self):
        """Technician receives 403 Forbidden attempting customer views."""
        self.client.login(username="tech_john", password="TechPassword123!")
        self.assertEqual(self.client.get(reverse("customers:customer_list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("customers:customer_create")).status_code, 403)
        self.assertEqual(self.client.get(reverse("customers:customer_detail", kwargs={"pk": self.cust1.pk})).status_code, 403)
        self.assertEqual(self.client.get(reverse("customers:customer_update", kwargs={"pk": self.cust1.pk})).status_code, 403)

    # =========================================================================
    # MODULE 3: DEVICE MANAGEMENT
    # =========================================================================

    def test_dev_01_register_device(self):
        """Registering a new device attaches properly to the customer."""
        self.client.login(username="admin_e2e", password="AdminPassword123!")
        res = self.client.post(
            reverse("customers:device_create"),
            {
                "customer": self.cust1.pk,
                "category": Device.Category.TABLET,
                "brand": "Apple",
                "model": "iPad Air 5",
                "serial_number": "IPAD-SN-9999",
                "accessories_received": "Apple Pencil",
                "condition_at_intake": "Pristine",
                "customer_reported_issue": "Will not charge past 1%",
            },
            follow=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(Device.objects.filter(serial_number="IPAD-SN-9999", customer=self.cust1).exists())
        self.assertContains(res, "iPad Air 5")

    def test_dev_02_device_search(self):
        """Device search returns matching equipment by serial, model, or brand."""
        self.client.login(username="admin_e2e", password="AdminPassword123!")
        res = self.client.get(reverse("customers:device_list"), {"q": "DELL-SN-1001"})
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Dell")
        self.assertContains(res, "XPS 15")
        self.assertNotContains(res, "APPL-SN-2002")

    def test_dev_03_deletion_protection(self):
        """Customer with registered devices cannot be deleted (on_delete=PROTECT)."""
        with self.assertRaises(ProtectedError):
            self.cust1.delete()

    def test_dev_04_mismatched_ownership_rejected(self):
        """Form validation blocks creating ticket with device belonging to another customer."""
        form = TicketCreateForm(
            data={
                "customer": self.cust1.pk,
                "device": self.dev2.pk,  # dev2 belongs to cust2!
                "priority": ServiceTicket.Priority.NORMAL,
                "issue_description": "Cross ownership test",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("device", form.errors)
        self.assertTrue(
            any("Select a valid choice" in str(err) or "does not belong to" in str(err) for err in form.errors["device"])
        )

    def test_dev_05_technician_blocked_from_device_management(self):
        """Technician receives 403 Forbidden attempting device management views."""
        self.client.login(username="tech_john", password="TechPassword123!")
        self.assertEqual(self.client.get(reverse("customers:device_list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("customers:device_create")).status_code, 403)
        self.assertEqual(self.client.get(reverse("customers:device_detail", kwargs={"pk": self.dev1.pk})).status_code, 403)
        self.assertEqual(self.client.get(reverse("customers:device_update", kwargs={"pk": self.dev1.pk})).status_code, 403)

    # =========================================================================
    # MODULE 4: SERVICE TICKET COMPLETE LIFECYCLE & WORKFLOW
    # =========================================================================

    def test_tick_01_intake_creates_unique_ticket_number(self):
        """Ticket intake auto-assigns RD-YYYY-XXXXX ticket number starting at RECEIVED."""
        self.client.login(username="admin_e2e", password="AdminPassword123!")
        res = self.client.post(
            reverse("tickets:ticket_create"),
            {
                "customer": self.cust1.pk,
                "device": self.dev1.pk,
                "priority": ServiceTicket.Priority.HIGH,
                "issue_description": "No power, LED blinks 3 amber 2 white",
                "estimated_cost": "150.00",
            },
            follow=True,
        )
        self.assertEqual(res.status_code, 200)
        ticket = ServiceTicket.objects.get(device=self.dev1)
        self.assertTrue(ticket.ticket_number.startswith("RD-"))
        self.assertEqual(ticket.status, ServiceTicket.Status.RECEIVED)
        self.assertEqual(ticket.priority, ServiceTicket.Priority.HIGH)
        self.assertEqual(ticket.estimated_cost, Decimal("150.00"))
        self.assertEqual(ticket.created_by, self.admin)

    def test_tick_02_negative_cost_rejected(self):
        """Submitting negative estimated cost fails validation."""
        self.client.login(username="admin_e2e", password="AdminPassword123!")
        res = self.client.post(
            reverse("tickets:ticket_create"),
            {
                "customer": self.cust1.pk,
                "device": self.dev1.pk,
                "priority": ServiceTicket.Priority.NORMAL,
                "issue_description": "Valid issue",
                "estimated_cost": "-20.00",
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertFalse(ServiceTicket.objects.filter(device=self.dev1).exists())

    def test_tick_03_technician_assignment_and_reassignment(self):
        """Admin assigns technician; subsequent reassignment tracks history atomically."""
        ticket = ServiceTicket.objects.create(
            customer=self.cust1,
            device=self.dev1,
            created_by=self.admin,
            issue_description="Diagnostic inspection",
        )
        self.client.login(username="admin_e2e", password="AdminPassword123!")

        # Initial assignment to Tech 1
        res1 = self.client.post(
            reverse("tickets:ticket_assign", kwargs={"pk": ticket.pk}),
            {"technician": self.tech1.pk, "notes": "Primary diagnostic"},
            follow=True,
        )
        self.assertEqual(res1.status_code, 200)
        ticket.refresh_from_db()
        self.assertEqual(ticket.assigned_technician, self.tech1)
        self.assertEqual(ticket.assignments.count(), 1)
        self.assertTrue(ticket.assignments.get(technician=self.tech1).is_current)

        # Reassignment to Tech 2
        res2 = self.client.post(
            reverse("tickets:ticket_assign", kwargs={"pk": ticket.pk}),
            {"technician": self.tech2.pk, "notes": "Handover to BGA specialist"},
            follow=True,
        )
        self.assertEqual(res2.status_code, 200)
        ticket.refresh_from_db()
        self.assertEqual(ticket.assigned_technician, self.tech2)
        self.assertEqual(ticket.assignments.count(), 2)
        self.assertFalse(ticket.assignments.get(technician=self.tech1).is_current)
        self.assertTrue(ticket.assignments.get(technician=self.tech2).is_current)

    def test_tick_04_full_state_machine_lifecycle(self):
        """Verifies complete end-to-end lifecycle progression from intake to delivery."""
        ticket = ServiceTicket.objects.create(
            customer=self.cust1,
            device=self.dev1,
            created_by=self.admin,
            assigned_technician=self.tech1,
            issue_description="Motherboard repair",
        )
        self.client.login(username="tech_john", password="TechPassword123!")

        # Step 1: RECEIVED -> UNDER_DIAGNOSIS
        res = self.client.post(
            reverse("tickets:ticket_status_update", kwargs={"pk": ticket.pk}),
            {"status": ServiceTicket.Status.UNDER_DIAGNOSIS, "reason": "Beginning diagnostic probe"},
            follow=True,
        )
        self.assertEqual(res.status_code, 200)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, ServiceTicket.Status.UNDER_DIAGNOSIS)

        # Step 2: Add Diagnostic Note
        res_note = self.client.post(
            reverse("tickets:repair_update_create", kwargs={"pk": ticket.pk}),
            {"update_type": RepairUpdate.UpdateType.DIAGNOSIS, "notes": "Found shorted capacitor on 19V rail."},
            follow=True,
        )
        self.assertEqual(res_note.status_code, 200)
        self.assertEqual(ticket.updates.count(), 1)

        # Step 3: UNDER_DIAGNOSIS -> IN_PROGRESS
        res = self.client.post(
            reverse("tickets:ticket_status_update", kwargs={"pk": ticket.pk}),
            {"status": ServiceTicket.Status.IN_PROGRESS, "reason": "Parts available, soldering now"},
            follow=True,
        )
        self.assertEqual(res.status_code, 200)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, ServiceTicket.Status.IN_PROGRESS)

        # Step 4: Attempting transition to ON_HOLD without reason fails validation
        res_bad = self.client.post(
            reverse("tickets:ticket_status_update", kwargs={"pk": ticket.pk}),
            {"status": ServiceTicket.Status.ON_HOLD, "reason": ""},
        )
        self.assertEqual(res_bad.status_code, 200)
        self.assertContains(res_bad, "A reason is required when placing a ticket on hold")

        # Step 5: IN_PROGRESS -> ON_HOLD (With Valid Reason)
        res = self.client.post(
            reverse("tickets:ticket_status_update", kwargs={"pk": ticket.pk}),
            {"status": ServiceTicket.Status.ON_HOLD, "reason": "Awaiting customer approval for thermal pads"},
            follow=True,
        )
        self.assertEqual(res.status_code, 200)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, ServiceTicket.Status.ON_HOLD)

        # Step 6: ON_HOLD -> IN_PROGRESS
        res = self.client.post(
            reverse("tickets:ticket_status_update", kwargs={"pk": ticket.pk}),
            {"status": ServiceTicket.Status.IN_PROGRESS, "reason": "Customer approved work"},
            follow=True,
        )
        self.assertEqual(res.status_code, 200)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, ServiceTicket.Status.IN_PROGRESS)

        # Step 7: Attempting transition to READY_FOR_DELIVERY without report fails
        self.client.login(username="admin_e2e", password="AdminPassword123!")
        res_premature = self.client.post(
            reverse("tickets:ticket_status_update", kwargs={"pk": ticket.pk}),
            {"status": ServiceTicket.Status.READY_FOR_DELIVERY, "reason": "Premature attempt"},
        )
        self.assertEqual(res_premature.status_code, 200)
        self.assertContains(res_premature, "without an approved Completion Report")

        # Step 8: Submit Completion Report (moves status to COMPLETED)
        self.client.login(username="tech_john", password="TechPassword123!")
        res_cr = self.client.post(
            reverse("tickets:completion_report_create", kwargs={"pk": ticket.pk}),
            {
                "diagnosis_summary": "19V rail shorted by PC102 ceramic capacitor",
                "work_performed": "Replaced PC102, cleaned PCB, stress-tested under FurMark for 2 hours.",
                "parts_replaced": "1x 10uF 25V SMD capacitor",
                "technician_remarks": "Passed 100% thermal and power benchmarks.",
            },
            follow=True,
        )
        self.assertEqual(res_cr.status_code, 200)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, ServiceTicket.Status.COMPLETED)
        self.assertTrue(hasattr(ticket, "completion_report"))

        # Step 9: COMPLETED -> READY_FOR_DELIVERY
        self.client.login(username="admin_e2e", password="AdminPassword123!")
        res_rfd = self.client.post(
            reverse("tickets:ticket_status_update", kwargs={"pk": ticket.pk}),
            {"status": ServiceTicket.Status.READY_FOR_DELIVERY, "reason": "Customer notified for pickup"},
            follow=True,
        )
        self.assertEqual(res_rfd.status_code, 200)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, ServiceTicket.Status.READY_FOR_DELIVERY)

        # Step 10: READY_FOR_DELIVERY -> DELIVERED
        res_del = self.client.post(
            reverse("tickets:ticket_status_update", kwargs={"pk": ticket.pk}),
            {"status": ServiceTicket.Status.DELIVERED, "reason": "Client picked up item, signed invoice"},
            follow=True,
        )
        self.assertEqual(res_del.status_code, 200)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, ServiceTicket.Status.DELIVERED)

        # Step 11: DELIVERED is terminal (no further transitions allowed for non-admin)
        self.client.login(username="tech_john", password="TechPassword123!")
        res_terminal = self.client.get(reverse("tickets:ticket_status_update", kwargs={"pk": ticket.pk}))
        # Status choices for terminal state should be empty
        self.assertEqual(len(res_terminal.context["form"].fields["status"].choices), 0)

    def test_tick_05_cancellation_workflow(self):
        """A received ticket can be cancelled with a required reason; cancelled tickets block completion reports."""
        ticket = ServiceTicket.objects.create(
            customer=self.cust1,
            device=self.dev1,
            created_by=self.admin,
            assigned_technician=self.tech1,
            issue_description="Initial intake for diagnostic",
        )
        self.client.login(username="admin_e2e", password="AdminPassword123!")

        # Cancel with reason
        res = self.client.post(
            reverse("tickets:ticket_status_update", kwargs={"pk": ticket.pk}),
            {"status": ServiceTicket.Status.CANCELLED, "reason": "Customer decided repair cost exceeds device value"},
            follow=True,
        )
        self.assertEqual(res.status_code, 200)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, ServiceTicket.Status.CANCELLED)

        # Attempting to submit completion report on cancelled ticket returns 403 Forbidden
        self.client.login(username="tech_john", password="TechPassword123!")
        res_cr = self.client.get(reverse("tickets:completion_report_create", kwargs={"pk": ticket.pk}))
        self.assertEqual(res_cr.status_code, 403)

    def test_tick_06_attachment_lifecycle_and_authorization(self):
        """Test attachment upload, magic byte check, authorized download, unauthorized rejection, and deletion."""
        ticket = ServiceTicket.objects.create(
            customer=self.cust1,
            device=self.dev1,
            created_by=self.admin,
            assigned_technician=self.tech1,
            issue_description="Attachment test",
        )
        self.client.login(username="tech_john", password="TechPassword123!")

        # 1. Upload valid PNG attachment
        png_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40
        fake_png = SimpleUploadedFile("board_inspection.png", png_data, content_type="image/png")
        res_up = self.client.post(
            reverse("tickets:attachment_upload", kwargs={"pk": ticket.pk}),
            {"file": fake_png, "caption": "Microscope board inspection"},
            follow=True,
        )
        self.assertEqual(res_up.status_code, 200)
        self.assertEqual(ticket.attachments.count(), 1)
        attachment = ticket.attachments.first()

        # 2. Download authorized for assigned tech
        res_down_tech = self.client.get(reverse("tickets:attachment_download", kwargs={"pk": attachment.pk}))
        try:
            self.assertEqual(res_down_tech.status_code, 200)
            self.assertEqual(res_down_tech.headers.get("X-Content-Type-Options"), "nosniff")
        finally:
            _close_response_files(res_down_tech)

        # 3. Download authorized for admin
        self.client.login(username="admin_e2e", password="AdminPassword123!")
        res_down_admin = self.client.get(reverse("tickets:attachment_download", kwargs={"pk": attachment.pk}))
        try:
            self.assertEqual(res_down_admin.status_code, 200)
        finally:
            _close_response_files(res_down_admin)

        # 4. Download rejected for unassigned tech (HTTP 403)
        self.client.login(username="tech_sarah", password="TechPassword123!")
        res_down_other = self.client.get(reverse("tickets:attachment_download", kwargs={"pk": attachment.pk}))
        try:
            self.assertEqual(res_down_other.status_code, 403)
        finally:
            _close_response_files(res_down_other)

        # 5. Delete attachment by uploader
        self.client.login(username="tech_john", password="TechPassword123!")
        res_del = self.client.post(reverse("tickets:attachment_delete", kwargs={"pk": attachment.pk}), follow=True)
        self.assertEqual(res_del.status_code, 200)
        self.assertEqual(ticket.attachments.count(), 0)

    # =========================================================================
    # MODULE 5: TECHNICIAN WORKSPACE & OBJECT PERMISSIONS
    # =========================================================================

    def test_tech_workspace_isolation(self):
        """Technician sees only assigned jobs and cannot access other technicians' jobs."""
        ticket_john = ServiceTicket.objects.create(
            customer=self.cust1,
            device=self.dev1,
            created_by=self.admin,
            assigned_technician=self.tech1,
            issue_description="John job",
        )
        ticket_sarah = ServiceTicket.objects.create(
            customer=self.cust2,
            device=self.dev2,
            created_by=self.admin,
            assigned_technician=self.tech2,
            issue_description="Sarah job",
        )
        ticket_unassigned = ServiceTicket.objects.create(
            customer=self.cust1,
            device=self.dev1,
            created_by=self.admin,
            issue_description="Unassigned job",
        )

        self.client.login(username="tech_john", password="TechPassword123!")

        # 1. My Jobs view contains only John's ticket
        res_my_jobs = self.client.get(reverse("tickets:my_jobs"))
        self.assertEqual(res_my_jobs.status_code, 200)
        self.assertContains(res_my_jobs, ticket_john.ticket_number)
        self.assertNotContains(res_my_jobs, ticket_sarah.ticket_number)
        self.assertNotContains(res_my_jobs, ticket_unassigned.ticket_number)

        # 2. John can view detail of his assigned ticket
        res_detail = self.client.get(ticket_john.get_absolute_url())
        self.assertEqual(res_detail.status_code, 200)
        self.assertContains(res_detail, "Alice Walker")
        self.assertContains(res_detail, "XPS 15")

        # 3. John is blocked with 403 from viewing Sarah's ticket
        res_sarah_detail = self.client.get(ticket_sarah.get_absolute_url())
        self.assertEqual(res_sarah_detail.status_code, 403)

        # 4. John is blocked with 403 from viewing unassigned ticket
        res_unassigned_detail = self.client.get(ticket_unassigned.get_absolute_url())
        self.assertEqual(res_unassigned_detail.status_code, 403)

        # 5. John cannot edit ticket metadata or reassign
        self.assertEqual(self.client.get(reverse("tickets:ticket_update", kwargs={"pk": ticket_john.pk})).status_code, 403)
        self.assertEqual(self.client.get(reverse("tickets:ticket_assign", kwargs={"pk": ticket_john.pk})).status_code, 403)

    # =========================================================================
    # MODULE 6: DASHBOARD, KPI CALCULATION & GLOBAL SEARCH
    # =========================================================================

    def test_dashboard_kpis_and_metrics_accuracy(self):
        """Dashboard overview KPI counts match exact database records."""
        # Provision tickets with specific states
        t1 = ServiceTicket.objects.create(customer=self.cust1, device=self.dev1, created_by=self.admin, issue_description="Issue 1", status=ServiceTicket.Status.RECEIVED)
        t2 = ServiceTicket.objects.create(customer=self.cust1, device=self.dev1, created_by=self.admin, assigned_technician=self.tech1, issue_description="Issue 2", status=ServiceTicket.Status.UNDER_DIAGNOSIS)
        t3 = ServiceTicket.objects.create(customer=self.cust2, device=self.dev2, created_by=self.admin, assigned_technician=self.tech1, issue_description="Issue 3", status=ServiceTicket.Status.IN_PROGRESS)
        t4 = ServiceTicket.objects.create(customer=self.cust2, device=self.dev2, created_by=self.admin, assigned_technician=self.tech2, issue_description="Issue 4", status=ServiceTicket.Status.ON_HOLD)
        t5 = ServiceTicket.objects.create(customer=self.cust1, device=self.dev1, created_by=self.admin, assigned_technician=self.tech2, issue_description="Issue 5", status=ServiceTicket.Status.COMPLETED)

        self.client.login(username="admin_e2e", password="AdminPassword123!")
        res = self.client.get(reverse("dashboard:overview"))
        self.assertEqual(res.status_code, 200)

        # Compare context data with actual DB counts
        self.assertEqual(res.context["total_tickets"], 5)
        self.assertEqual(res.context["received_count"], 1)
        self.assertEqual(res.context["in_progress_count"], 2)  # under_diagnosis + in_progress
        self.assertEqual(res.context["on_hold_count"], 1)
        self.assertEqual(res.context["completed_count"], 1)
        self.assertEqual(res.context["unassigned_count"], 1)

        # Verify Chart JSON payload
        status_json = json.loads(res.context["status_counts_json"])
        self.assertEqual(status_json["received"], 1)
        self.assertEqual(status_json["under_diagnosis"], 1)
        self.assertEqual(status_json["in_progress"], 1)
        self.assertEqual(status_json["on_hold"], 1)
        self.assertEqual(status_json["completed"], 1)

    def test_operational_reports_view(self):
        """Operational reports renders breakdown and turnaround statistics."""
        self.client.login(username="admin_e2e", password="AdminPassword123!")
        res = self.client.get(reverse("dashboard:reports"), {"range": "30d"})
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Operational Reports &amp; Analytics")
        self.assertContains(res, "Equipment Category Breakdown")

    def test_global_search_functionality(self):
        """Global search locates tickets, customers, and devices by keyword."""
        ticket = ServiceTicket.objects.create(
            customer=self.cust1,
            device=self.dev1,
            created_by=self.admin,
            issue_description="Searchable motherboard issue",
        )
        self.client.login(username="admin_e2e", password="AdminPassword123!")

        # Search by exact ticket number redirects directly to ticket detail
        res_ticket = self.client.get(reverse("dashboard:search"), {"q": ticket.ticket_number}, follow=True)
        self.assertEqual(res_ticket.status_code, 200)
        self.assertIn(ticket.get_absolute_url(), [r[0] for r in res_ticket.redirect_chain])
        self.assertContains(res_ticket, ticket.ticket_number)

        # Search by keyword renders search results page
        res_kw = self.client.get(reverse("dashboard:search"), {"q": "Searchable"})
        self.assertEqual(res_kw.status_code, 200)
        self.assertContains(res_kw, ticket.ticket_number)

        # Search by customer name
        res_cust = self.client.get(reverse("dashboard:search"), {"q": "Alice"})
        self.assertEqual(res_cust.status_code, 200)
        self.assertContains(res_cust, "Alice Walker")

        # Search by device serial number
        res_dev = self.client.get(reverse("dashboard:search"), {"q": "DELL-SN-1001"})
        self.assertEqual(res_dev.status_code, 200)
        self.assertContains(res_dev, "DELL-SN-1001")

        # Technician blocked from global search
        self.client.login(username="tech_john", password="TechPassword123!")
        self.assertEqual(self.client.get(reverse("dashboard:search"), {"q": "Alice"}).status_code, 403)

    # =========================================================================
    # MODULE 7: UI RENDERING, NAVIGATION & ERROR TEMPLATES
    # =========================================================================

    def test_ui_navigation_and_custom_error_pages(self):
        """Tests tailored navigation links and custom 403/404 error template rendering."""
        # 1. Admin navbar links
        self.client.login(username="admin_e2e", password="AdminPassword123!")
        res_admin = self.client.get(reverse("dashboard:overview"))
        self.assertContains(res_admin, reverse("dashboard:overview"))
        self.assertContains(res_admin, reverse("tickets:ticket_list"))
        self.assertContains(res_admin, reverse("customers:customer_list"))
        self.assertContains(res_admin, reverse("customers:device_list"))
        self.assertContains(res_admin, reverse("dashboard:reports"))

        # 2. Technician navbar links (only My Jobs; no admin routes)
        self.client.login(username="tech_john", password="TechPassword123!")
        res_tech = self.client.get(reverse("tickets:my_jobs"))
        self.assertContains(res_tech, reverse("tickets:my_jobs"))
        self.assertNotContains(res_tech, reverse("dashboard:overview"))
        self.assertNotContains(res_tech, reverse("customers:customer_list"))
        self.assertNotContains(res_tech, reverse("dashboard:reports"))

        # 3. Custom 404 Not Found response
        res_404 = self.client.get("/non-existent-route-for-testing/")
        self.assertEqual(res_404.status_code, 404)
        self.assertContains(res_404, "HTTP 404 Not Found", status_code=404)
        self.assertContains(res_404, "Resource Not Found", status_code=404)

        # 4. Custom 403 Forbidden response
        res_403 = self.client.get(reverse("customers:customer_list"))
        self.assertEqual(res_403.status_code, 403)
        self.assertContains(res_403, "HTTP 403 Forbidden", status_code=403)
        self.assertContains(res_403, "Access Denied", status_code=403)
