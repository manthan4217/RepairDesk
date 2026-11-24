"""Automated tests for Customer Management and Device Registry (Phase 2)."""

from django.contrib.auth import get_user_model
from django.db.models import ProtectedError
from django.test import TestCase
from django.urls import reverse

from .forms import CustomerForm, DeviceForm
from .models import Customer, Device

User = get_user_model()


class CustomerModelTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(
            name="John Doe",
            phone="+91 98765 43210",
            email="john@example.com",
            address="123 High Street, Mumbai",
        )

    def test_customer_creation_and_str(self):
        self.assertEqual(str(self.customer), "John Doe (+91 98765 43210)")
        self.assertTrue(self.customer.is_active)
        self.assertEqual(self.customer.total_devices, 0)

    def test_customer_absolute_url(self):
        self.assertEqual(
            self.customer.get_absolute_url(),
            reverse("customers:customer_detail", kwargs={"pk": self.customer.pk}),
        )


class DeviceModelTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(
            name="Acme Corp",
            phone="9988776655",
            email="support@acme.org",
        )
        self.device = Device.objects.create(
            customer=self.customer,
            category=Device.Category.LAPTOP,
            brand="Dell",
            model="Latitude 5420",
            serial_number="DL-5420-XYZ",
            condition_at_intake="Small scratch on top lid",
            accessories_received="Charger 65W",
            customer_reported_issue="Battery drains rapidly within 20 minutes",
        )

    def test_device_creation_and_str(self):
        expected_str = f"Dell Latitude 5420 [SN: DL-5420-XYZ] - Acme Corp"
        self.assertEqual(str(self.device), expected_str)
        self.assertEqual(self.customer.total_devices, 1)

    def test_protected_deletion_rule(self):
        """Deleting a customer with linked devices must raise ProtectedError."""
        with self.assertRaises(ProtectedError):
            self.customer.delete()

        # The records must still exist intact
        self.assertTrue(Customer.objects.filter(pk=self.customer.pk).exists())
        self.assertTrue(Device.objects.filter(pk=self.device.pk).exists())


class CustomerFormValidationTests(TestCase):
    def test_valid_customer_form(self):
        form = CustomerForm(
            data={
                "name": "Alice Smith",
                "phone": "+91 98765 12345",
                "email": "alice@example.com",
                "address": "45 Park Road",
                "notes": "Prefers evening contact",
                "is_active": True,
            }
        )
        self.assertTrue(form.is_valid())

    def test_invalid_short_phone_rejected(self):
        form = CustomerForm(
            data={
                "name": "Bob",
                "phone": "123",  # Too short
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("phone", form.errors)


class CustomerViewsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="staff_user",
            password="testpassword123",
            role=User.Role.ADMINISTRATOR,
        )
        self.customer = Customer.objects.create(
            name="Alpha Services",
            phone="9876500000",
            email="info@alpha.com",
        )

    def test_unauthenticated_user_redirected_to_login(self):
        response = self.client.get(reverse("customers:customer_list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_customer_list_view(self):
        self.client.login(username="staff_user", password="testpassword123")
        response = self.client.get(reverse("customers:customer_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alpha Services")
        self.assertContains(response, "9876500000")

    def test_customer_search_filtering(self):
        self.client.login(username="staff_user", password="testpassword123")
        Customer.objects.create(name="Beta Enterprises", phone="1122334455")

        # Search by Alpha
        response = self.client.get(reverse("customers:customer_list"), {"q": "Alpha"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alpha Services")
        self.assertNotContains(response, "Beta Enterprises")

        # Search by phone
        response_phone = self.client.get(reverse("customers:customer_list"), {"q": "1122334455"})
        self.assertEqual(response_phone.status_code, 200)
        self.assertContains(response_phone, "Beta Enterprises")
        self.assertNotContains(response_phone, "Alpha Services")

    def test_customer_create_view(self):
        self.client.login(username="staff_user", password="testpassword123")
        response = self.client.post(
            reverse("customers:customer_create"),
            {
                "name": "Charlie Brown",
                "phone": "9998887776",
                "email": "charlie@example.com",
                "address": "Green Avenue",
                "is_active": True,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Customer.objects.filter(name="Charlie Brown").exists())
        self.assertContains(response, "Charlie Brown")

    def test_customer_detail_view(self):
        self.client.login(username="staff_user", password="testpassword123")
        response = self.client.get(self.customer.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alpha Services")
        self.assertContains(response, "9876500000")

    def test_customer_update_view(self):
        self.client.login(username="staff_user", password="testpassword123")
        response = self.client.post(
            reverse("customers:customer_update", kwargs={"pk": self.customer.pk}),
            {
                "name": "Alpha Services Updated",
                "phone": "9876500000",
                "email": "updated@alpha.com",
                "is_active": True,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.name, "Alpha Services Updated")
        self.assertEqual(self.customer.email, "updated@alpha.com")

    def test_customer_toggle_status_view(self):
        self.client.login(username="staff_user", password="testpassword123")
        self.assertTrue(self.customer.is_active)

        # Toggle to archived
        response = self.client.post(
            reverse("customers:customer_toggle_status", kwargs={"pk": self.customer.pk}),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.customer.refresh_from_db()
        self.assertFalse(self.customer.is_active)


class DeviceViewsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="tech_tester",
            password="testpassword123",
            role=User.Role.TECHNICIAN,
        )
        self.customer = Customer.objects.create(
            name="David Miller",
            phone="8887776665",
            email="david@example.com",
        )
        self.device = Device.objects.create(
            customer=self.customer,
            category=Device.Category.SMARTPHONE,
            brand="Samsung",
            model="Galaxy S22",
            serial_number="SM-G901-XYZ",
            customer_reported_issue="Cracked screen glass, touch still working",
        )

    def test_device_list_view(self):
        self.client.login(username="tech_tester", password="testpassword123")
        response = self.client.get(reverse("customers:device_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Samsung Galaxy S22")
        self.assertContains(response, "David Miller")

    def test_device_search_filtering(self):
        self.client.login(username="tech_tester", password="testpassword123")
        # Search by serial number
        response = self.client.get(reverse("customers:device_list"), {"q": "SM-G901-XYZ"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Samsung Galaxy S22")

        # Search by non-existent serial
        response_empty = self.client.get(reverse("customers:device_list"), {"q": "NONEXISTENT"})
        self.assertEqual(response_empty.status_code, 200)
        self.assertNotContains(response_empty, "SM-G901-XYZ")

    def test_device_create_view(self):
        self.client.login(username="tech_tester", password="testpassword123")
        response = self.client.post(
            reverse("customers:device_create") + f"?customer={self.customer.pk}",
            {
                "customer": self.customer.pk,
                "category": Device.Category.LAPTOP,
                "brand": "Lenovo",
                "model": "ThinkPad T14",
                "serial_number": "TP-T14-001",
                "condition_at_intake": "Minor palm rest wear",
                "accessories_received": "USB-C Charger",
                "customer_reported_issue": "Keys 'E' and 'R' not responding",
                "is_active": True,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Device.objects.filter(model="ThinkPad T14").exists())
        self.assertContains(response, "ThinkPad T14")

    def test_device_detail_view(self):
        self.client.login(username="tech_tester", password="testpassword123")
        response = self.client.get(self.device.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Samsung Galaxy S22")
        self.assertContains(response, "SM-G901-XYZ")
        self.assertContains(response, "David Miller")
        self.assertContains(response, "Cracked screen glass")

    def test_device_update_view(self):
        self.client.login(username="tech_tester", password="testpassword123")
        response = self.client.post(
            reverse("customers:device_update", kwargs={"pk": self.device.pk}),
            {
                "customer": self.customer.pk,
                "category": Device.Category.SMARTPHONE,
                "brand": "Samsung",
                "model": "Galaxy S22 Ultra",
                "serial_number": "SM-G901-XYZ",
                "condition_at_intake": "Cracked screen",
                "accessories_received": "None",
                "customer_reported_issue": "Screen replacement requested",
                "is_active": True,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.device.refresh_from_db()
        self.assertEqual(self.device.model, "Galaxy S22 Ultra")
