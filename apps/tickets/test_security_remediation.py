"""Automated tests verifying Phase 2 Security Remediation (SEC-01 through SEC-14)."""

import io
import os
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.customers.models import Customer, Device
from apps.tickets.forms import AttachmentUploadForm, TicketUpdateForm
from apps.tickets.models import Attachment, ServiceTicket

User = get_user_model()


class SecurityRemediationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin_sec",
            password="testpassword",
            role=User.Role.ADMINISTRATOR,
            is_staff=True,
            is_superuser=True,
        )
        self.tech_assigned = User.objects.create_user(
            username="tech_assigned",
            password="testpassword",
            role=User.Role.TECHNICIAN,
        )
        self.tech_other = User.objects.create_user(
            username="tech_other",
            password="testpassword",
            role=User.Role.TECHNICIAN,
        )
        self.customer = Customer.objects.create(name="Secure Customer", phone="9988776655")
        self.device = Device.objects.create(
            customer=self.customer,
            category=Device.Category.LAPTOP,
            brand="Dell",
            model="Latitude 5420",
            serial_number="LAT-5420-SEC",
        )
        self.ticket = ServiceTicket.objects.create(
            customer=self.customer,
            device=self.device,
            created_by=self.admin,
            assigned_technician=self.tech_assigned,
            issue_description="Diagnostic inspection",
        )

        # Create sample JPEG attachment
        jpeg_content = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 50
        fake_file = SimpleUploadedFile("sample.jpg", jpeg_content, content_type="image/jpeg")
        self.attachment = Attachment.objects.create(
            ticket=self.ticket,
            uploaded_by=self.tech_assigned,
            file=fake_file,
            caption="Intake photo",
        )

    def tearDown(self):
        # Clean up files created during test
        if hasattr(self, "attachment") and self.attachment.file:
            try:
                self.attachment.file.close()
                self.attachment.file.delete(save=False)
            except Exception:
                pass

    # SEC-01: Media / Attachment Authorization Tests
    def test_attachment_download_authorized_for_admin_and_assigned_tech(self):
        url = reverse("tickets:attachment_download", kwargs={"pk": self.attachment.pk})

        # Admin access
        self.client.login(username="admin_sec", password="testpassword")
        res_admin = self.client.get(url)
        self.assertEqual(res_admin.status_code, 200)
        self.assertEqual(res_admin.headers.get("X-Content-Type-Options"), "nosniff")
        res_admin.close()

        # Assigned tech access
        self.client.login(username="tech_assigned", password="testpassword")
        res_tech = self.client.get(url)
        self.assertEqual(res_tech.status_code, 200)
        self.assertEqual(res_tech.headers.get("X-Content-Type-Options"), "nosniff")
        res_tech.close()

    def test_attachment_download_denied_for_unassigned_tech_and_anonymous(self):
        url = reverse("tickets:attachment_download", kwargs={"pk": self.attachment.pk})

        # Unassigned tech gets 403
        self.client.login(username="tech_other", password="testpassword")
        res_other = self.client.get(url)
        self.assertEqual(res_other.status_code, 403)
        res_other.close()

        # Anonymous gets redirected to login
        self.client.logout()
        res_anon = self.client.get(url)
        self.assertEqual(res_anon.status_code, 302)
        self.assertIn("/accounts/login/", res_anon.url)
        res_anon.close()

    # SEC-02: Device Enumeration API RBAC
    def test_customer_devices_api_restricted_to_admin(self):
        url = reverse("tickets:customer_devices_api", kwargs={"customer_id": self.customer.pk})

        # Admin gets 200 with device data
        self.client.login(username="admin_sec", password="testpassword")
        res_admin = self.client.get(url)
        self.assertEqual(res_admin.status_code, 200)
        data = res_admin.json()
        self.assertEqual(len(data["devices"]), 1)
        self.assertEqual(data["devices"][0]["id"], self.device.pk)

        # Technician gets 403 Forbidden
        self.client.login(username="tech_assigned", password="testpassword")
        res_tech = self.client.get(url)
        self.assertEqual(res_tech.status_code, 403)

        # Anonymous redirected
        self.client.logout()
        res_anon = self.client.get(url)
        self.assertEqual(res_anon.status_code, 302)

    # SEC-03: UserLogoutView strictly POST-only
    def test_logout_get_method_not_allowed(self):
        self.client.login(username="admin_sec", password="testpassword")
        res = self.client.get(reverse("accounts:logout"))
        self.assertEqual(res.status_code, 405)

    def test_logout_post_succeeds(self):
        self.client.login(username="admin_sec", password="testpassword")
        res = self.client.post(reverse("accounts:logout"), follow=True)
        self.assertEqual(res.status_code, 200)

    # SEC-04: TicketUpdateForm does not expose status
    def test_ticket_update_form_does_not_contain_status(self):
        form = TicketUpdateForm()
        self.assertNotIn("status", form.fields)

    # SEC-05: Binary Magic Byte Validation
    def test_attachment_upload_magic_byte_validation(self):
        # Fake image file with text content
        spoofed_file = SimpleUploadedFile("malicious.jpg", b"<?php echo 'malicious'; ?>", content_type="image/jpeg")
        form = AttachmentUploadForm(files={"file": spoofed_file}, data={"caption": "Test"})
        self.assertFalse(form.is_valid())
        self.assertIn("file", form.errors)
        self.assertIn("Invalid file type or corrupt file header", form.errors["file"][0])

        # Valid PNG magic bytes
        png_content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
        valid_png = SimpleUploadedFile("valid.png", png_content, content_type="image/png")
        form_png = AttachmentUploadForm(files={"file": valid_png}, data={"caption": "Valid PNG"})
        self.assertTrue(form_png.is_valid())

        # Valid PDF magic bytes
        pdf_content = b"%PDF-1.5 test document content"
        valid_pdf = SimpleUploadedFile("valid.pdf", pdf_content, content_type="application/pdf")
        form_pdf = AttachmentUploadForm(files={"file": valid_pdf}, data={"caption": "Valid PDF"})
        self.assertTrue(form_pdf.is_valid())

    # SEC-14: Cancelled ticket rejects completion report
    def test_completion_report_rejected_on_cancelled_ticket(self):
        self.ticket.status = ServiceTicket.Status.CANCELLED
        self.ticket.save(update_fields=["status"])

        url = reverse("tickets:completion_report_create", kwargs={"pk": self.ticket.pk})

        self.client.login(username="admin_sec", password="testpassword")
        res_admin = self.client.get(url)
        self.assertEqual(res_admin.status_code, 403)

        self.client.login(username="tech_assigned", password="testpassword")
        res_tech = self.client.get(url)
        self.assertEqual(res_tech.status_code, 403)

    # SEC-10: Seed demo data safeguard
    @override_settings(DEBUG=False)
    def test_seed_demo_data_blocked_when_debug_false_without_force(self):
        out = io.StringIO()
        with self.assertRaises(CommandError) as ctx:
            call_command("seed_demo_data", stdout=out)
        self.assertIn("Security Safeguard", str(ctx.exception))
