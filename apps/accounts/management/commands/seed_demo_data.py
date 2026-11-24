"""Management command to populate RepairDesk with demo accounts, customers, devices, and tickets."""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import User
from apps.customers.models import Customer, Device
from apps.tickets.models import Assignment, RepairUpdate, ServiceTicket


class Command(BaseCommand):
    help = "Populate the database with realistic demo accounts and sample service tickets."

    def handle(self, *args, **options):
        with transaction.atomic():
            # 1. Administrator Account
            admin_user, admin_created = User.objects.get_or_create(
                username="admin",
                defaults={
                    "role": User.Role.ADMINISTRATOR,
                    "display_name": "System Administrator",
                    "email": "admin@repairdesk.local",
                    "is_staff": True,
                    "is_superuser": True,
                },
            )
            if admin_created:
                admin_user.set_password("admin123")
                admin_user.save()
                self.stdout.write(self.style.SUCCESS("Created Admin: 'admin' (password: 'admin123')"))
            else:
                self.stdout.write("Admin 'admin' already exists.")

            # 2. Technician Account
            tech_user, tech_created = User.objects.get_or_create(
                username="tech_alex",
                defaults={
                    "role": User.Role.TECHNICIAN,
                    "display_name": "Alex Rivera",
                    "email": "alex@repairdesk.local",
                    "phone": "+91 98765 43211",
                    "is_staff": True,
                },
            )
            if tech_created:
                tech_user.set_password("tech123")
                tech_user.save()
                self.stdout.write(self.style.SUCCESS("Created Technician: 'tech_alex' (password: 'tech123')"))
            else:
                self.stdout.write("Technician 'tech_alex' already exists.")

            # 3. Sample Customers
            cust1, _ = Customer.objects.get_or_create(
                phone="9876543210",
                defaults={
                    "name": "Rajesh Sharma",
                    "email": "rajesh.sharma@example.com",
                    "address": "Flat 402, Lotus Towers, Bangalore",
                },
            )
            cust2, _ = Customer.objects.get_or_create(
                phone="9811223344",
                defaults={
                    "name": "Priya Patel",
                    "email": "priya.patel@example.com",
                    "address": "B-12 Sunrise Enclave, Mumbai",
                },
            )

            # 4. Sample Devices
            dev1, _ = Device.objects.get_or_create(
                customer=cust1,
                serial_number="DELL-XPS-9520",
                defaults={
                    "category": Device.Category.LAPTOP,
                    "brand": "Dell",
                    "model": "XPS 15 (9520)",
                    "customer_reported_issue": "Screen flickering and battery draining rapidly.",
                    "condition_at_intake": "Minor scuff on top lid, keyboard intact.",
                    "accessories_received": "Original 130W USB-C Charger",
                },
            )
            dev2, _ = Device.objects.get_or_create(
                customer=cust2,
                serial_number="APL-IP14P-8821",
                defaults={
                    "category": Device.Category.SMARTPHONE,
                    "brand": "Apple",
                    "model": "iPhone 14 Pro",
                    "customer_reported_issue": "Cracked rear glass panel and bottom speaker distortion.",
                    "condition_at_intake": "Shattered back glass, screen protector applied.",
                    "accessories_received": "None (device only)",
                },
            )

            # 5. Sample Tickets
            if not ServiceTicket.objects.filter(device=dev1).exists():
                ticket1 = ServiceTicket.objects.create(
                    customer=cust1,
                    device=dev1,
                    created_by=admin_user,
                    priority=ServiceTicket.Priority.HIGH,
                    status=ServiceTicket.Status.UNDER_DIAGNOSIS,
                    issue_description="Customer reports intermittent display flickering during GPU load. Battery capacity degraded below 50%.",
                    estimated_cost=8500.00,
                )
                ticket1.assign_to(
                    technician=tech_user,
                    assigned_by=admin_user,
                    notes="Please inspect display ribbon cable and run battery cell test.",
                )
                RepairUpdate.objects.create(
                    ticket=ticket1,
                    author=tech_user,
                    update_type=RepairUpdate.UpdateType.DIAGNOSIS,
                    notes="Display eDP cable properly seated. Panel T-Con board shows intermittent voltage drop. Ordered OEM battery replacement.",
                )
                self.stdout.write(self.style.SUCCESS(f"Created active ticket: {ticket1.ticket_number} (Assigned to {tech_user.username})"))

            if not ServiceTicket.objects.filter(device=dev2).exists():
                ticket2 = ServiceTicket.objects.create(
                    customer=cust2,
                    device=dev2,
                    created_by=admin_user,
                    priority=ServiceTicket.Priority.NORMAL,
                    status=ServiceTicket.Status.RECEIVED,
                    issue_description="Rear camera glass intact, back glass chassis broken. Speaker grill clogged with debris causing muffled audio output.",
                    estimated_cost=4500.00,
                )
                self.stdout.write(self.style.SUCCESS(f"Created unassigned ticket: {ticket2.ticket_number}"))

        self.stdout.write(self.style.SUCCESS("\nRepairDesk demo data loaded successfully!"))
