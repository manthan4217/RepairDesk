"""Automated tests verifying Phase 3: Database Integrity, Concurrency & Lifecycle Guarantees."""

from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.customers.models import Customer, Device
from apps.tickets.forms import TicketAssignForm
from apps.tickets.models import Assignment, CompletionReport, ServiceTicket
from apps.tickets.services import generate_ticket_number

User = get_user_model()


class DatabaseIntegrityTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin_db",
            password="testpassword",
            role=User.Role.ADMINISTRATOR,
            is_staff=True,
            is_superuser=True,
        )
        self.technician = User.objects.create_user(
            username="tech_db",
            password="testpassword",
            role=User.Role.TECHNICIAN,
        )
        self.inactive_technician = User.objects.create_user(
            username="tech_inactive",
            password="testpassword",
            role=User.Role.TECHNICIAN,
            is_active=False,
        )
        self.customer = Customer.objects.create(name="DB Integrity Client", phone="9988112233")
        self.device = Device.objects.create(
            customer=self.customer,
            category=Device.Category.LAPTOP,
            brand="Lenovo",
            model="ThinkPad T14",
            serial_number="TP-T14-DB",
        )
        self.ticket = ServiceTicket.objects.create(
            customer=self.customer,
            device=self.device,
            created_by=self.admin,
            assigned_technician=self.technician,
            issue_description="Keyboard replacement required",
        )

    # DB-03: Lifecycle integrity enforcement in clean()
    def test_clean_enforces_completion_report_for_delivery_statuses(self):
        # Setting ready_for_delivery without completion report must fail clean()
        self.ticket.status = ServiceTicket.Status.READY_FOR_DELIVERY
        with self.assertRaises(ValidationError) as ctx:
            self.ticket.clean()
        self.assertIn("status", ctx.exception.message_dict)

        # Setting delivered without completion report must fail clean()
        self.ticket.status = ServiceTicket.Status.DELIVERED
        with self.assertRaises(ValidationError) as ctx:
            self.ticket.clean()
        self.assertIn("status", ctx.exception.message_dict)

        # Creating completion report allows ready_for_delivery
        CompletionReport.objects.create(
            ticket=self.ticket,
            technician=self.technician,
            diagnosis_summary="Spilled coffee on keyboard",
            work_performed="Replaced keyboard assembly and tested all keys",
        )
        self.ticket.clean()  # should not raise

    # DB-05: Technician role validation on assignment
    def test_assign_to_rejects_non_technician_user(self):
        with self.assertRaises(ValidationError) as ctx:
            self.ticket.assign_to(
                technician=self.admin,
                assigned_by=self.admin,
                notes="Assigning to admin should fail",
            )
        self.assertIn("not a designated technician", str(ctx.exception))

    def test_assign_to_rejects_inactive_technician(self):
        with self.assertRaises(ValidationError) as ctx:
            self.ticket.assign_to(
                technician=self.inactive_technician,
                assigned_by=self.admin,
                notes="Assigning to inactive tech should fail",
            )
        self.assertIn("Cannot assign job to inactive user", str(ctx.exception))

    def test_ticket_assign_form_filters_technicians_only(self):
        form = TicketAssignForm()
        tech_pks = set(form.fields["technician"].queryset.values_list("pk", flat=True))
        self.assertIn(self.technician.pk, tech_pks)
        self.assertNotIn(self.admin.pk, tech_pks)
        self.assertNotIn(self.inactive_technician.pk, tech_pks)

    # DB-07: Estimated cost non-negative validation
    def test_negative_estimated_cost_rejected_in_clean(self):
        self.ticket.estimated_cost = Decimal("-25.50")
        with self.assertRaises(ValidationError):
            self.ticket.full_clean()

    # DB-01: Sequencer extra_offset functionality
    def test_generate_ticket_number_supports_offset(self):
        base_candidate = generate_ticket_number(extra_offset=0)
        offset_candidate = generate_ticket_number(extra_offset=1)
        base_seq = int(base_candidate.split("-")[-1])
        offset_seq = int(offset_candidate.split("-")[-1])
        self.assertEqual(offset_seq, base_seq + 1)

    # DB-08: Row lock assignment atomic consistency
    def test_assign_to_updates_is_current_atomically(self):
        second_tech = User.objects.create_user(
            username="tech_second_db",
            password="testpassword",
            role=User.Role.TECHNICIAN,
        )
        self.ticket.assign_to(self.technician, assigned_by=self.admin, notes="Initial")
        self.assertEqual(self.ticket.assignments.filter(is_current=True).count(), 1)
        self.assertEqual(self.ticket.assignments.get(is_current=True).technician, self.technician)

        self.ticket.assign_to(second_tech, assigned_by=self.admin, notes="Reassigned")
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.assigned_technician, second_tech)
        self.assertEqual(self.ticket.assignments.filter(is_current=True).count(), 1)
        self.assertEqual(self.ticket.assignments.get(is_current=True).technician, second_tech)
        self.assertEqual(self.ticket.assignments.filter(is_current=False).count(), 1)
