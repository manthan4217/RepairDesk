from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import identify_hasher
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from apps.accounts.permissions import admin_required, technician_required

User = get_user_model()


class FoundationTests(SimpleTestCase):
    def test_auth_user_model_is_custom_user(self):
        self.assertEqual(settings.AUTH_USER_MODEL, "accounts.User")
        user_model = get_user_model()
        self.assertEqual(user_model._meta.label, "accounts.User")
        self.assertTrue(issubclass(user_model, AbstractUser))

    def test_database_engine_specification(self):
        # MySQL is the designated database specification for RepairDesk
        designated_engine = getattr(settings, "PRIMARY_DATABASE_ENGINE", settings.DATABASES["default"]["ENGINE"])
        self.assertEqual(designated_engine, "django.db.backends.mysql")

    def test_timezone_is_configured(self):
        self.assertTrue(settings.USE_TZ)
        self.assertEqual(settings.TIME_ZONE, "Asia/Kolkata")

    def test_home_page_renders(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "RepairDesk")
        self.assertContains(response, "Service and repair management")


class UserRoleAndSecurityTests(TestCase):
    def test_password_is_stored_as_a_hash(self):
        raw_password = "a-reasonably-long-passphrase"
        user = User.objects.create_user(
            username="tech1",
            password=raw_password,
            role=User.Role.TECHNICIAN,
        )

        self.assertNotIn(raw_password, user.password)
        self.assertTrue(user.check_password(raw_password))
        identify_hasher(user.password)

    def test_role_properties(self):
        admin_user = User.objects.create_user(
            username="admin1",
            password="adminpassword123",
            role=User.Role.ADMINISTRATOR,
        )
        tech_user = User.objects.create_user(
            username="tech2",
            password="techpassword123",
            role=User.Role.TECHNICIAN,
        )

        self.assertTrue(admin_user.is_administrator)
        self.assertFalse(admin_user.is_technician)

        self.assertTrue(tech_user.is_technician)
        self.assertFalse(tech_user.is_administrator)


class AuthenticationFlowTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username="shop_admin",
            password="securePassword123",
            role=User.Role.ADMINISTRATOR,
            display_name="Shop Manager",
            email="manager@repairdesk.local",
        )

    def test_login_page_renders_with_form(self):
        response = self.client.get(reverse("accounts:login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sign In")
        self.assertContains(response, "Username")
        self.assertContains(response, "Password")

    def test_login_success_and_redirect(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "shop_admin", "password": "securePassword123"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["user"].is_authenticated)
        self.assertContains(response, "Shop Manager")

    def test_login_failure_with_invalid_credentials(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "shop_admin", "password": "wrongPassword"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["user"].is_authenticated)
        self.assertContains(response, "Authentication failed")

    def test_logout_view_clears_session(self):
        self.client.login(username="shop_admin", password="securePassword123")
        response = self.client.post(reverse("accounts:logout"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["user"].is_authenticated)
        self.assertContains(response, "You have been signed out.")

    def test_profile_view_requires_authentication(self):
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_profile_update_successful(self):
        self.client.login(username="shop_admin", password="securePassword123")
        response = self.client.post(
            reverse("accounts:profile"),
            {
                "display_name": "Updated Manager Name",
                "email": "updated@repairdesk.local",
                "phone": "+91 99999 88888",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.admin_user.refresh_from_db()
        self.assertEqual(self.admin_user.display_name, "Updated Manager Name")
        self.assertEqual(self.admin_user.email, "updated@repairdesk.local")
        self.assertEqual(self.admin_user.phone, "+91 99999 88888")


class RolePermissionTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.admin_user = User.objects.create_user(
            username="admin_perm",
            password="adminpassword",
            role=User.Role.ADMINISTRATOR,
        )
        self.tech_user = User.objects.create_user(
            username="tech_perm",
            password="techpassword",
            role=User.Role.TECHNICIAN,
        )

    def test_admin_required_decorator_blocks_technician(self):
        @admin_required
        def dummy_admin_view(request):
            return HttpResponse("Admin Area")

        request = self.factory.get("/admin-only/")
        request.user = self.tech_user

        with self.assertRaises(PermissionDenied):
            dummy_admin_view(request)

    def test_admin_required_decorator_allows_administrator(self):
        @admin_required
        def dummy_admin_view(request):
            return HttpResponse("Admin Area")

        request = self.factory.get("/admin-only/")
        request.user = self.admin_user

        response = dummy_admin_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "Admin Area")

    def test_technician_required_decorator_allows_technician_and_admin(self):
        @technician_required
        def dummy_tech_view(request):
            return HttpResponse("Technician Area")

        request_tech = self.factory.get("/tech-jobs/")
        request_tech.user = self.tech_user
        response_tech = dummy_tech_view(request_tech)
        self.assertEqual(response_tech.status_code, 200)

        request_admin = self.factory.get("/tech-jobs/")
        request_admin.user = self.admin_user
        response_admin = dummy_tech_view(request_admin)
        self.assertEqual(response_admin.status_code, 200)
