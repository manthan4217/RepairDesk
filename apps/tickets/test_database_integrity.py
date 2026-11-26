"""Automated tests verifying Phase 3 & Phase 5: Database Integrity, Concurrency & Lifecycle Guarantees."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
import threading

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, connections, transaction
from django.db.models import ProtectedError
from django.test import TestCase, TransactionTestCase

from apps.customers.models import Customer, Device
from apps.tickets.forms import TicketAssignForm
from apps.tickets.models import Assignment, CompletionReport, RepairUpdate, ServiceTicket, StatusHistory
from apps.tickets.services import generate_ticket_number

User = get_user_model()


class DatabaseIntegrityTests(TestCase):
    """Verifies relational constraints, check constraints, foreign keys, and transaction integrity."""

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

    # --- DB-01: Ticket number generation and extra_offset ---
    def test_generate_ticket_number_supports_offset(self):
        base_candidate = generate_ticket_number(extra_offset=0)
        offset_candidate = generate_ticket_number(extra_offset=1)
        base_seq = int(base_candidate.split("-")[-1])
        offset_seq = int(offset_candidate.split("-")[-1])
        self.assertEqual(offset_seq, base_seq + 1)

    # --- DB-02: Foreign Key Enforcement in MySQL ---
    def test_foreign_key_enforcement_at_database_level(self):
        """MySQL InnoDB must reject child rows with non-existent foreign keys."""
        with connection.cursor() as cursor:
            with self.assertRaises(IntegrityError):
                cursor.execute(
                    "INSERT INTO tickets_serviceticket "
                    "(ticket_number, customer_id, device_id, created_by_id, issue_description, status, priority, created_at, updated_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())",
                    ["RD-9999-99999", 999999, self.device.pk, self.admin.pk, "Invalid FK Test", "received", "normal"],
                )

    # --- DB-03: Unique Ticket Number Enforcement in MySQL ---
    def test_unique_ticket_number_enforced_at_database_level(self):
        """MySQL InnoDB must enforce UNIQUE constraint on ticket_number."""
        with connection.cursor() as cursor:
            with self.assertRaises(IntegrityError):
                cursor.execute(
                    "INSERT INTO tickets_serviceticket "
                    "(ticket_number, customer_id, device_id, created_by_id, issue_description, status, priority, created_at, updated_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())",
                    [self.ticket.ticket_number, self.customer.pk, self.device.pk, self.admin.pk, "Duplicate Number", "received", "normal"],
                )

    # --- DB-04: MySQL 8.0 CHECK Constraints ---
    def test_mysql_check_constraint_ticket_status_valid(self):
        """MySQL 8.0 must reject invalid status values at the database level."""
        with connection.cursor() as cursor:
            with self.assertRaises(IntegrityError) as ctx:
                cursor.execute(
                    "INSERT INTO tickets_serviceticket "
                    "(ticket_number, customer_id, device_id, created_by_id, issue_description, status, priority, created_at, updated_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())",
                    ["RD-2026-90001", self.customer.pk, self.device.pk, self.admin.pk, "Bad Status Test", "invalid_status", "normal"],
                )
            self.assertIn("ticket_status_valid", str(ctx.exception).lower())

    def test_mysql_check_constraint_ticket_priority_valid(self):
        """MySQL 8.0 must reject invalid priority values at the database level."""
        with connection.cursor() as cursor:
            with self.assertRaises(IntegrityError) as ctx:
                cursor.execute(
                    "INSERT INTO tickets_serviceticket "
                    "(ticket_number, customer_id, device_id, created_by_id, issue_description, status, priority, created_at, updated_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())",
                    ["RD-2026-90002", self.customer.pk, self.device.pk, self.admin.pk, "Bad Priority Test", "received", "super_urgent"],
                )
            self.assertIn("ticket_priority_valid", str(ctx.exception).lower())

    def test_mysql_check_constraint_ticket_estimated_cost_non_negative(self):
        """MySQL 8.0 must reject negative estimated_cost at the database level."""
        with connection.cursor() as cursor:
            with self.assertRaises(IntegrityError) as ctx:
                cursor.execute(
                    "INSERT INTO tickets_serviceticket "
                    "(ticket_number, customer_id, device_id, created_by_id, issue_description, status, priority, estimated_cost, created_at, updated_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())",
                    ["RD-2026-90003", self.customer.pk, self.device.pk, self.admin.pk, "Bad Cost Test", "received", "normal", -25.00],
                )
            self.assertIn("ticket_estimated_cost_non_negative", str(ctx.exception).lower())

    def test_mysql_check_constraint_accounts_user_role_valid(self):
        """MySQL 8.0 must reject invalid user roles at the database level."""
        with connection.cursor() as cursor:
            with self.assertRaises(IntegrityError) as ctx:
                cursor.execute(
                    "INSERT INTO accounts_user "
                    "(password, is_superuser, username, first_name, last_name, email, is_staff, is_active, date_joined, role, phone, display_name) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, %s, %s)",
                    ["pbkdf2_test", 0, "bad_role_user", "", "", "", 0, 1, "unauthorized_role", "", ""],
                )
            self.assertIn("accounts_user_role_valid", str(ctx.exception).lower())

    # --- DB-05: PROTECT Deletion Enforcement ---
    def test_protect_deletion_customer_with_active_devices_and_tickets(self):
        """Deleting a customer with registered devices and tickets must be protected."""
        with self.assertRaises(ProtectedError):
            self.customer.delete()

    def test_protect_deletion_device_with_tickets(self):
        """Deleting a device associated with service tickets must be protected."""
        with self.assertRaises(ProtectedError):
            self.device.delete()

    def test_protect_deletion_technician_with_recorded_assignments(self):
        """Deleting a user who is referenced by assignments or completion reports must be protected."""
        self.ticket.assign_to(self.technician, assigned_by=self.admin, notes="Initial Assignment")
        with self.assertRaises(ProtectedError):
            self.technician.delete()

    # --- DB-06: CASCADE Deletion on Tickets ---
    def test_cascade_deletion_ticket_removes_related_records(self):
        """Deleting a ticket must cascade to delete assignments, updates, and status histories."""
        self.ticket.assign_to(self.technician, assigned_by=self.admin, notes="Audit Test")
        RepairUpdate.objects.create(
            ticket=self.ticket,
            author=self.technician,
            update_type=RepairUpdate.UpdateType.PROGRESS,
            notes="Testing cascade cleanup",
        )
        CompletionReport.objects.create(
            ticket=self.ticket,
            technician=self.technician,
            diagnosis_summary="Clean diagnosis",
            work_performed="Clean repair",
        )

        ticket_id = self.ticket.pk
        self.ticket.delete()

        self.assertFalse(Assignment.objects.filter(ticket_id=ticket_id).exists())
        self.assertFalse(RepairUpdate.objects.filter(ticket_id=ticket_id).exists())
        self.assertFalse(StatusHistory.objects.filter(ticket_id=ticket_id).exists())
        self.assertFalse(CompletionReport.objects.filter(ticket_id=ticket_id).exists())

    # --- DB-07: Technician Role Validation ---
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

    def test_negative_estimated_cost_rejected_in_clean(self):
        self.ticket.estimated_cost = Decimal("-25.50")
        with self.assertRaises(ValidationError):
            self.ticket.full_clean()

    # --- DB-08: Completion Report Requirements & Lifecycle ---
    def test_clean_enforces_completion_report_for_delivery_statuses(self):
        self.ticket.status = ServiceTicket.Status.READY_FOR_DELIVERY
        with self.assertRaises(ValidationError) as ctx:
            self.ticket.clean()
        self.assertIn("status", ctx.exception.message_dict)

        self.ticket.status = ServiceTicket.Status.DELIVERED
        with self.assertRaises(ValidationError) as ctx:
            self.ticket.clean()
        self.assertIn("status", ctx.exception.message_dict)

        CompletionReport.objects.create(
            ticket=self.ticket,
            technician=self.technician,
            diagnosis_summary="Spilled coffee on keyboard",
            work_performed="Replaced keyboard assembly and tested all keys",
        )
        self.ticket.clean()

    def test_update_status_enforces_completion_report_before_delivery(self):
        # Ticket must first be in COMPLETED to allow forward transition to READY_FOR_DELIVERY
        self.ticket.status = ServiceTicket.Status.COMPLETED
        self.ticket.save(update_fields=["status"])
        with self.assertRaises(ValidationError) as ctx:
            self.ticket.update_status(ServiceTicket.Status.READY_FOR_DELIVERY, user=self.technician)
        self.assertIn("Completion Report", str(ctx.exception))

    # --- DB-09: Ticket Status Transition State Machine ---
    def test_ticket_status_transition_state_machine(self):
        """Status transitions must adhere to ALLOWED_TRANSITIONS rules."""
        # Non-admin cannot jump from received directly to delivered
        with self.assertRaises(ValidationError):
            self.ticket.update_status(ServiceTicket.Status.DELIVERED, user=self.technician)

        # Valid forward transitions
        self.ticket.update_status(ServiceTicket.Status.UNDER_DIAGNOSIS, user=self.technician)
        self.assertEqual(self.ticket.status, ServiceTicket.Status.UNDER_DIAGNOSIS)

        self.ticket.update_status(ServiceTicket.Status.IN_PROGRESS, user=self.technician)
        self.assertEqual(self.ticket.status, ServiceTicket.Status.IN_PROGRESS)

        self.ticket.update_status(ServiceTicket.Status.COMPLETED, user=self.technician)
        self.assertEqual(self.ticket.status, ServiceTicket.Status.COMPLETED)

        # Admin override allows direct transition even outside standard flow
        self.ticket.update_status(ServiceTicket.Status.ON_HOLD, user=self.admin, reason="Admin hold override")
        self.assertEqual(self.ticket.status, ServiceTicket.Status.ON_HOLD)

    # --- DB-10: Multi-Step Transaction Rollback ---
    def test_multi_step_transaction_rollback_on_failure(self):
        """Operations within an atomic block must completely roll back if any step fails."""
        initial_ticket_count = ServiceTicket.objects.count()
        initial_assignment_count = Assignment.objects.count()

        try:
            with transaction.atomic():
                new_ticket = ServiceTicket.objects.create(
                    customer=self.customer,
                    device=self.device,
                    created_by=self.admin,
                    issue_description="Will be rolled back",
                )
                Assignment.objects.create(
                    ticket=new_ticket,
                    technician=self.technician,
                    assigned_by=self.admin,
                    notes="Temp Assignment",
                )
                raise RuntimeError("Simulated mid-operation transaction failure")
        except RuntimeError:
            pass

        self.assertEqual(ServiceTicket.objects.count(), initial_ticket_count)
        self.assertEqual(Assignment.objects.count(), initial_assignment_count)

    # --- DB-11: Row Lock Assignment Atomic Consistency ---
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


class DatabaseConcurrencyTests(TransactionTestCase):
    """Verifies concurrency safety, row locking, and duplicate prevention under load on MySQL."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin_conc",
            password="testpassword",
            role=User.Role.ADMINISTRATOR,
            is_staff=True,
            is_superuser=True,
        )
        self.customer = Customer.objects.create(name="Concurrency Client", phone="9988776655")
        self.device = Device.objects.create(
            customer=self.customer,
            category=Device.Category.LAPTOP,
            brand="Dell",
            model="XPS 15",
            serial_number="XPS-CONC-01",
        )

    # --- CONC-01: Concurrent Ticket Creation Under Load ---
    def test_concurrent_ticket_creation_generates_unique_numbers(self):
        """Simultaneous ticket creation across multiple threads must produce unique, non-colliding numbers."""
        num_threads = 8
        created_tickets = []
        errors = []

        def worker(thread_idx):
            try:
                ticket = ServiceTicket.objects.create(
                    customer=self.customer,
                    device=self.device,
                    created_by=self.admin,
                    issue_description=f"Concurrent Intake Thread {thread_idx}",
                )
                return ticket.ticket_number
            except Exception as e:
                errors.append(f"Thread {thread_idx} failed: {type(e).__name__}: {e}")
                return None
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker, i) for i in range(num_threads)]
            for future in as_completed(futures):
                res = future.result()
                if res:
                    created_tickets.append(res)

        self.assertEqual(errors, [], f"Encountered unexpected errors during concurrent creation: {errors}")
        self.assertEqual(len(created_tickets), num_threads)
        self.assertEqual(
            len(set(created_tickets)),
            num_threads,
            f"Duplicate ticket numbers generated: {created_tickets}",
        )

    # --- CONC-02: Concurrent Technician Reassignment Row Locking ---
    def test_concurrent_technician_assignment_row_locking(self):
        """Simultaneous technician assignments on the same ticket must be serialized by row locks."""
        ticket = ServiceTicket.objects.create(
            customer=self.customer,
            device=self.device,
            created_by=self.admin,
            issue_description="Reassignment test ticket",
        )

        techs = [
            User.objects.create_user(
                username=f"tech_conc_{i}",
                password="testpassword",
                role=User.Role.TECHNICIAN,
            )
            for i in range(4)
        ]

        errors = []

        def assign_worker(tech):
            try:
                ticket.assign_to(tech, assigned_by=self.admin, notes=f"Assigned to {tech.username}")
            except Exception as e:
                errors.append(f"Assignment to {tech.username} failed: {type(e).__name__}: {e}")
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(assign_worker, t) for t in techs]
            for f in as_completed(futures):
                f.result()

        self.assertEqual(errors, [], f"Encountered errors during concurrent assignment: {errors}")

        ticket.refresh_from_db()
        current_assignments = ticket.assignments.filter(is_current=True)
        self.assertEqual(current_assignments.count(), 1, "Exactly one assignment must be active (is_current=True)")
        self.assertEqual(ticket.assigned_technician, current_assignments.first().technician)
        self.assertEqual(ticket.assignments.count(), 4, "All 4 assignment history records must be preserved")

    # --- CONC-03: Concurrent Status Updates with Row Locking ---
    def test_concurrent_status_updates_row_locking(self):
        """Simultaneous status update attempts must execute cleanly under select_for_update."""
        ticket = ServiceTicket.objects.create(
            customer=self.customer,
            device=self.device,
            created_by=self.admin,
            issue_description="Status lock test",
        )

        errors = []

        def status_worker(status, reason):
            try:
                ticket.update_status(status, user=self.admin, reason=reason)
            except Exception as e:
                errors.append(f"Status update to {status} failed: {type(e).__name__}: {e}")
            finally:
                connections.close_all()

        # Update through a sequence of statuses concurrently
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(status_worker, ServiceTicket.Status.UNDER_DIAGNOSIS, "Reason 1"),
                executor.submit(status_worker, ServiceTicket.Status.IN_PROGRESS, "Reason 2"),
                executor.submit(status_worker, ServiceTicket.Status.ON_HOLD, "Reason 3"),
            ]
            for f in as_completed(futures):
                f.result()

        self.assertEqual(errors, [])
        ticket.refresh_from_db()
        self.assertIn(ticket.status, [
            ServiceTicket.Status.UNDER_DIAGNOSIS,
            ServiceTicket.Status.IN_PROGRESS,
            ServiceTicket.Status.ON_HOLD,
        ])
        self.assertGreaterEqual(ticket.status_history.count(), 1)

    # --- CONC-04: Concurrent Completion Report Duplicate Prevention ---
    def test_concurrent_completion_report_creation_prevented(self):
        """Simultaneous creation of completion reports on the same ticket must enforce uniqueness."""
        tech = User.objects.create_user(
            username="tech_report_conc",
            password="testpassword",
            role=User.Role.TECHNICIAN,
        )
        ticket = ServiceTicket.objects.create(
            customer=self.customer,
            device=self.device,
            created_by=self.admin,
            assigned_technician=tech,
            issue_description="Completion report lock test",
        )

        success_count = [0]
        integrity_error_count = [0]
        lock = threading.Lock()

        def report_worker(worker_id):
            try:
                CompletionReport.objects.create(
                    ticket=ticket,
                    technician=tech,
                    diagnosis_summary=f"Diagnosis from worker {worker_id}",
                    work_performed=f"Work from worker {worker_id}",
                )
                with lock:
                    success_count[0] += 1
            except IntegrityError:
                with lock:
                    integrity_error_count[0] += 1
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(report_worker, 1)
            f2 = executor.submit(report_worker, 2)
            f1.result()
            f2.result()

        self.assertEqual(success_count[0], 1, "Exactly one thread must succeed in creating the CompletionReport")
        self.assertEqual(integrity_error_count[0], 1, "The competing thread must be blocked by IntegrityError")
        self.assertEqual(CompletionReport.objects.filter(ticket=ticket).count(), 1)
