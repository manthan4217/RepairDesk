"""Automated tests for Service Tickets, Assignments, Notes, and Lifecycle (Phase 3 & 4)."""

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.customers.models import Customer, Device
from .forms import AttachmentUploadForm, CompletionReportForm, RepairUpdateForm, StatusTransitionForm, TicketCreateForm
from .models import Assignment, Attachment, CompletionReport, RepairUpdate, ServiceTicket, StatusHistory
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
            device=self.device2,
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


class LifecycleAndStateMachineTests(TestCase):
    def setUp(self):
        self.tech_user = User.objects.create_user(
            username="tech_john",
            password="testpassword",
            role=User.Role.TECHNICIAN,
        )
        self.customer = Customer.objects.create(name="Omega Corp", phone="5556667777")
        self.device = Device.objects.create(
            customer=self.customer,
            category=Device.Category.LAPTOP,
            brand="Lenovo",
            model="ThinkPad X1",
            customer_reported_issue="Keyboard keys sticking",
        )
        self.ticket = ServiceTicket.objects.create(
            customer=self.customer,
            device=self.device,
            created_by=self.tech_user,
            assigned_technician=self.tech_user,
            status=ServiceTicket.Status.RECEIVED,
            issue_description="Keyboard keys sticking",
        )

    def test_valid_status_transitions(self):
        # RECEIVED -> UNDER_DIAGNOSIS
        self.ticket.update_status(ServiceTicket.Status.UNDER_DIAGNOSIS, self.tech_user, reason="Started bench inspection")
        self.assertEqual(self.ticket.status, ServiceTicket.Status.UNDER_DIAGNOSIS)
        self.assertEqual(self.ticket.status_history.count(), 1)

        # UNDER_DIAGNOSIS -> IN_PROGRESS
        self.ticket.update_status(ServiceTicket.Status.IN_PROGRESS, self.tech_user, reason="Disassembling chassis")
        self.assertEqual(self.ticket.status, ServiceTicket.Status.IN_PROGRESS)

        # IN_PROGRESS -> COMPLETED
        self.ticket.update_status(ServiceTicket.Status.COMPLETED, self.tech_user, reason="Cleaned membrane switches")
        self.assertEqual(self.ticket.status, ServiceTicket.Status.COMPLETED)
        self.assertEqual(self.ticket.status_history.count(), 3)

    def test_invalid_status_transition_rejected(self):
        """Technician jumping straight from RECEIVED to DELIVERED must be rejected."""
        with self.assertRaises(ValidationError):
            self.ticket.update_status(ServiceTicket.Status.DELIVERED, self.tech_user)

    def test_delivery_requires_completion_report(self):
        """Attempting to transition from COMPLETED to READY_FOR_DELIVERY without a CompletionReport must fail."""
        self.ticket.status = ServiceTicket.Status.COMPLETED
        self.ticket.save()

        with self.assertRaises(ValidationError):
            self.ticket.update_status(ServiceTicket.Status.READY_FOR_DELIVERY, self.tech_user)

        # Now attach a CompletionReport
        CompletionReport.objects.create(
            ticket=self.ticket,
            technician=self.tech_user,
            diagnosis_summary="Liquid ingress on keyboard",
            work_performed="Replaced top case assembly",
        )

        # Now transition should succeed
        self.ticket.update_status(ServiceTicket.Status.READY_FOR_DELIVERY, self.tech_user, reason="QC Passed")
        self.assertEqual(self.ticket.status, ServiceTicket.Status.READY_FOR_DELIVERY)


class RepairUpdateAndReportTests(TestCase):
    def setUp(self):
        self.tech = User.objects.create_user(username="tech_mike", password="testpassword", role=User.Role.TECHNICIAN)
        self.customer = Customer.objects.create(name="Delta Ltd", phone="9988112233")
        self.device = Device.objects.create(
            customer=self.customer,
            category=Device.Category.DESKTOP,
            brand="HP",
            model="ProDesk 400",
            customer_reported_issue="No POST",
        )
        self.ticket = ServiceTicket.objects.create(
            customer=self.customer,
            device=self.device,
            created_by=self.tech,
            assigned_technician=self.tech,
            issue_description="No POST issue",
        )

    def test_repair_update_creation(self):
        update = RepairUpdate.objects.create(
            ticket=self.ticket,
            author=self.tech,
            update_type=RepairUpdate.UpdateType.DIAGNOSIS,
            notes="RAM stick in slot 2 is faulty. Tested with spare DDR4 and boots to UEFI.",
        )
        self.assertEqual(self.ticket.updates.count(), 1)
        self.assertEqual(update.get_update_type_display(), "Diagnosis Finding")
        self.assertIn("tech_mike", str(update))

    def test_completion_report_creation(self):
        report = CompletionReport.objects.create(
            ticket=self.ticket,
            technician=self.tech,
            diagnosis_summary="Defective 8GB DDR4 RAM stick",
            work_performed="Installed 8GB DDR4 3200MHz RAM and completed 2 passes of MemTest86",
            parts_replaced="1x 8GB DDR4 Module",
            technician_remarks="Advised customer to keep chassis vents clear of dust",
        )
        self.assertTrue(hasattr(self.ticket, "completion_report"))
        self.assertEqual(self.ticket.completion_report, report)


class TechnicianWorkspaceViewsTests(TestCase):
    def setUp(self):
        self.tech_a = User.objects.create_user(username="tech_alice", password="testpassword", role=User.Role.TECHNICIAN)
        self.tech_b = User.objects.create_user(username="tech_bob", password="testpassword", role=User.Role.TECHNICIAN)
        self.customer = Customer.objects.create(name="Customer A", phone="1234567890")
        self.device_a = Device.objects.create(
            customer=self.customer,
            category=Device.Category.LAPTOP,
            brand="Dell",
            model="Inspiron",
            customer_reported_issue="Screen flickering",
        )
        self.device_b = Device.objects.create(
            customer=self.customer,
            category=Device.Category.SMARTPHONE,
            brand="OnePlus",
            model="11",
            customer_reported_issue="Mic not working",
        )

        self.ticket_a = ServiceTicket.objects.create(
            customer=self.customer,
            device=self.device_a,
            created_by=self.tech_a,
            assigned_technician=self.tech_a,
            issue_description="Screen flickering",
        )
        self.ticket_b = ServiceTicket.objects.create(
            customer=self.customer,
            device=self.device_b,
            created_by=self.tech_b,
            assigned_technician=self.tech_b,
            issue_description="Mic not working",
        )

    def test_my_jobs_list_view_filters_by_technician(self):
        """Technician A should only see Ticket A in their My Jobs queue."""
        self.client.login(username="tech_alice", password="testpassword")
        response = self.client.get(reverse("tickets:my_jobs"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.ticket_a.ticket_number)
        self.assertNotContains(response, self.ticket_b.ticket_number)

    def test_repair_update_create_view(self):
        self.client.login(username="tech_alice", password="testpassword")
        response = self.client.post(
            reverse("tickets:repair_update_create", kwargs={"pk": self.ticket_a.pk}),
            {
                "update_type": RepairUpdate.UpdateType.PROGRESS,
                "notes": "EDP cable reseated and test display running.",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.ticket_a.updates.count(), 1)
        self.assertContains(response, "EDP cable reseated")

    def test_status_transition_view(self):
        self.client.login(username="tech_alice", password="testpassword")
        response = self.client.post(
            reverse("tickets:ticket_status_update", kwargs={"pk": self.ticket_a.pk}),
            {
                "status": ServiceTicket.Status.UNDER_DIAGNOSIS,
                "reason": "Starting diagnosis",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.ticket_a.refresh_from_db()
        self.assertEqual(self.ticket_a.status, ServiceTicket.Status.UNDER_DIAGNOSIS)

    def test_completion_report_view(self):
        self.ticket_a.status = ServiceTicket.Status.IN_PROGRESS
        self.ticket_a.save()

        self.client.login(username="tech_alice", password="testpassword")
        response = self.client.post(
            reverse("tickets:completion_report_create", kwargs={"pk": self.ticket_a.pk}),
            {
                "diagnosis_summary": "Loose LVDS connector pins",
                "work_performed": "Cleaned connector and secured with Kapton tape",
                "parts_replaced": "None",
                "technician_remarks": "Passed 24hr stress test",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.ticket_a.refresh_from_db()
        self.assertTrue(hasattr(self.ticket_a, "completion_report"))
        self.assertEqual(self.ticket_a.status, ServiceTicket.Status.COMPLETED)
        self.assertContains(response, "Signed Completion Report")

    def test_idor_protection_other_technician_blocked(self):
        """Tech Bob attempting to add a repair update to Tech Alice's ticket must receive 403 Forbidden."""
        self.client.login(username="tech_bob", password="testpassword")
        response = self.client.post(
            reverse("tickets:repair_update_create", kwargs={"pk": self.ticket_a.pk}),
            {
                "update_type": RepairUpdate.UpdateType.PROGRESS,
                "notes": "Unauthorized note from Bob",
            },
        )
        self.assertEqual(response.status_code, 403)


class AttachmentTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin_user",
            password="testpassword",
            role=User.Role.ADMINISTRATOR,
        )
        self.tech_alice = User.objects.create_user(
            username="tech_alice",
            password="testpassword",
            role=User.Role.TECHNICIAN,
        )
        self.tech_bob = User.objects.create_user(
            username="tech_bob",
            password="testpassword",
            role=User.Role.TECHNICIAN,
        )
        self.customer = Customer.objects.create(name="Attachment Customer", phone="9988776655")
        self.device = Device.objects.create(
            customer=self.customer,
            category=Device.Category.SMARTPHONE,
            brand="Samsung",
            model="Galaxy S22",
        )
        self.ticket = ServiceTicket.objects.create(
            customer=self.customer,
            device=self.device,
            assigned_technician=self.tech_alice,
            created_by=self.admin,
            issue_description="Inspect cracked camera lens",
        )

    def test_attachment_properties_and_upload_success(self):
        self.client.login(username="tech_alice", password="testpassword")
        test_file = SimpleUploadedFile(
            "lens_damage.jpg",
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00",
            content_type="image/jpeg",
        )
        response = self.client.post(
            reverse("tickets:attachment_upload", kwargs={"pk": self.ticket.pk}),
            {
                "file": test_file,
                "caption": "Cracked back camera lens photo",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.ticket.attachments.count(), 1)
        att = self.ticket.attachments.first()
        self.assertEqual(att.uploaded_by, self.tech_alice)
        self.assertEqual(att.caption, "Cracked back camera lens photo")
        self.assertTrue(att.is_image)
        self.assertContains(response, "Cracked back camera lens photo")

    def test_attachment_upload_pdf_document(self):
        self.client.login(username="tech_alice", password="testpassword")
        pdf_file = SimpleUploadedFile(
            "diagnostic_report.pdf",
            b"%PDF-1.4 test dummy content",
            content_type="application/pdf",
        )
        response = self.client.post(
            reverse("tickets:attachment_upload", kwargs={"pk": self.ticket.pk}),
            {
                "file": pdf_file,
                "caption": "Hardware test result PDF",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        att = self.ticket.attachments.first()
        self.assertFalse(att.is_image)
        self.assertContains(response, "Hardware test result PDF")

    def test_attachment_upload_disallowed_extension(self):
        self.client.login(username="tech_alice", password="testpassword")
        script_file = SimpleUploadedFile(
            "malicious.exe",
            b"MZ executable content",
            content_type="application/octet-stream",
        )
        response = self.client.post(
            reverse("tickets:attachment_upload", kwargs={"pk": self.ticket.pk}),
            {
                "file": script_file,
                "caption": "Executable file",
            },
            follow=True,
        )
        self.assertEqual(self.ticket.attachments.count(), 0)

    def test_attachment_upload_size_limit_form_validation(self):
        # 6MB dummy content exceeds 5MB limit
        large_file = SimpleUploadedFile(
            "large_file.png",
            b"0" * (6 * 1024 * 1024),
            content_type="image/png",
        )
        form = AttachmentUploadForm(files={"file": large_file}, data={"caption": "Big file"})
        self.assertFalse(form.is_valid())
        self.assertIn("file", form.errors)
        self.assertIn("File size exceeds the 5MB limit.", form.errors["file"][0])

    def test_attachment_delete_by_uploader(self):
        test_file = SimpleUploadedFile("delete_me.png", b"test", content_type="image/png")
        att = Attachment.objects.create(
            ticket=self.ticket,
            uploaded_by=self.tech_alice,
            file=test_file,
            caption="Temporary upload",
        )
        self.client.login(username="tech_alice", password="testpassword")
        response = self.client.post(
            reverse("tickets:attachment_delete", kwargs={"pk": att.pk}),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.ticket.attachments.count(), 0)

    def test_attachment_delete_by_admin(self):
        test_file = SimpleUploadedFile("delete_by_admin.png", b"test", content_type="image/png")
        att = Attachment.objects.create(
            ticket=self.ticket,
            uploaded_by=self.tech_alice,
            file=test_file,
            caption="Tech upload deleted by admin",
        )
        self.client.login(username="admin_user", password="testpassword")
        response = self.client.post(
            reverse("tickets:attachment_delete", kwargs={"pk": att.pk}),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.ticket.attachments.count(), 0)

    def test_attachment_delete_blocked_for_other_technician(self):
        test_file = SimpleUploadedFile("protected.png", b"test", content_type="image/png")
        att = Attachment.objects.create(
            ticket=self.ticket,
            uploaded_by=self.tech_alice,
            file=test_file,
            caption="Alice file",
        )
        self.client.login(username="tech_bob", password="testpassword")
        response = self.client.post(
            reverse("tickets:attachment_delete", kwargs={"pk": att.pk}),
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.ticket.attachments.count(), 1)


class TicketAdminViewsRBACSecurityTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="admin_rbac", password="testpassword", role=User.Role.ADMINISTRATOR)
        self.tech = User.objects.create_user(username="tech_rbac", password="testpassword", role=User.Role.TECHNICIAN)
        self.customer = Customer.objects.create(name="RBAC Customer", phone="9988771122")
        self.device = Device.objects.create(
            customer=self.customer,
            category=Device.Category.LAPTOP,
            brand="Dell",
            model="XPS 15",
            customer_reported_issue="Keyboard issue",
        )
        self.ticket = ServiceTicket.objects.create(
            customer=self.customer,
            device=self.device,
            created_by=self.admin,
            assigned_technician=self.tech,
            issue_description="Keyboard keys sticking",
        )

    def test_admin_can_access_ticket_intake_update_and_assign(self):
        self.client.login(username="admin_rbac", password="testpassword")
        self.assertEqual(self.client.get(reverse("tickets:ticket_create")).status_code, 200)
        self.assertEqual(self.client.get(reverse("tickets:ticket_update", kwargs={"pk": self.ticket.pk})).status_code, 200)
        self.assertEqual(self.client.get(reverse("tickets:ticket_assign", kwargs={"pk": self.ticket.pk})).status_code, 200)

    def test_technician_blocked_from_ticket_intake_update_and_assign(self):
        self.client.login(username="tech_rbac", password="testpassword")
        self.assertEqual(self.client.get(reverse("tickets:ticket_create")).status_code, 403)
        self.assertEqual(self.client.get(reverse("tickets:ticket_update", kwargs={"pk": self.ticket.pk})).status_code, 403)
        self.assertEqual(self.client.get(reverse("tickets:ticket_assign", kwargs={"pk": self.ticket.pk})).status_code, 403)

    def test_object_level_ticket_detail_access(self):
        # Admin can view any ticket
        self.client.login(username="admin_rbac", password="testpassword")
        self.assertEqual(self.client.get(self.ticket.get_absolute_url()).status_code, 200)

        # Assigned technician can view their assigned ticket
        self.client.login(username="tech_rbac", password="testpassword")
        self.assertEqual(self.client.get(self.ticket.get_absolute_url()).status_code, 200)

        # Unassigned ticket -> technician gets 403 Forbidden
        unassigned_ticket = ServiceTicket.objects.create(
            customer=self.customer,
            device=self.device,
            created_by=self.admin,
            issue_description="Unassigned job",
        )
        self.assertEqual(self.client.get(unassigned_ticket.get_absolute_url()).status_code, 403)

        # Another technician accessing this ticket gets 403 Forbidden
        other_tech = User.objects.create_user(username="tech_other", password="testpassword", role=User.Role.TECHNICIAN)
        self.client.login(username="tech_other", password="testpassword")
        self.assertEqual(self.client.get(self.ticket.get_absolute_url()).status_code, 403)

        # Non-existent ticket returns 404
        self.assertEqual(self.client.get(reverse("tickets:ticket_detail", kwargs={"pk": 99999})).status_code, 404)

    def test_technician_specific_ticket_listing(self):
        other_tech = User.objects.create_user(username="tech_second", password="testpassword", role=User.Role.TECHNICIAN)
        other_ticket = ServiceTicket.objects.create(
            customer=self.customer,
            device=self.device,
            created_by=self.admin,
            assigned_technician=other_tech,
            issue_description="Other tech ticket",
        )
        unassigned_ticket = ServiceTicket.objects.create(
            customer=self.customer,
            device=self.device,
            created_by=self.admin,
            issue_description="Unassigned ticket",
        )

        # Admin sees all tickets
        self.client.login(username="admin_rbac", password="testpassword")
        res_admin = self.client.get(reverse("tickets:ticket_list"))
        self.assertEqual(res_admin.status_code, 200)
        self.assertContains(res_admin, self.ticket.ticket_number)
        self.assertContains(res_admin, other_ticket.ticket_number)
        self.assertContains(res_admin, unassigned_ticket.ticket_number)

        # Technician sees only their own assigned ticket
        self.client.login(username="tech_rbac", password="testpassword")
        res_tech = self.client.get(reverse("tickets:ticket_list"))
        self.assertEqual(res_tech.status_code, 200)
        self.assertContains(res_tech, self.ticket.ticket_number)
        self.assertNotContains(res_tech, other_ticket.ticket_number)
        self.assertNotContains(res_tech, unassigned_ticket.ticket_number)
