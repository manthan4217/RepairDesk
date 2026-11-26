"""Unit tests for production database configuration, DATABASE_URL precedence, and settings."""

import importlib
import os
from unittest import mock

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase


class DatabaseConfigurationTests(SimpleTestCase):
    """Test DATABASE_URL parsing, DB_* fallback, and production guard assertions."""

    def test_whitenoise_middleware_configured_after_security_middleware(self):
        """Verify WhiteNoiseMiddleware is installed immediately after SecurityMiddleware."""
        middleware = settings.MIDDLEWARE
        self.assertIn("whitenoise.middleware.WhiteNoiseMiddleware", middleware)
        self.assertIn("django.middleware.security.SecurityMiddleware", middleware)

        security_idx = middleware.index("django.middleware.security.SecurityMiddleware")
        whitenoise_idx = middleware.index("whitenoise.middleware.WhiteNoiseMiddleware")
        self.assertEqual(
            whitenoise_idx,
            security_idx + 1,
            "WhiteNoiseMiddleware must immediately follow SecurityMiddleware",
        )

    def test_storages_configuration(self):
        """Verify STORAGES dictionary defines CompressedManifestStaticFilesStorage."""
        storages = settings.STORAGES
        self.assertIn("default", storages)
        self.assertIn("staticfiles", storages)
        self.assertEqual(
            storages["staticfiles"]["BACKEND"],
            "whitenoise.storage.CompressedManifestStaticFilesStorage",
        )
        self.assertEqual(
            storages["default"]["BACKEND"],
            "django.core.files.storage.FileSystemStorage",
        )

    def test_csrf_trusted_origins_parsing(self):
        """Verify CSRF_TRUSTED_ORIGINS setting exists and is loaded from environment as a list."""
        self.assertIsInstance(settings.CSRF_TRUSTED_ORIGINS, list)

        # Test parsing comma-separated origins with django-environ
        import environ
        env = environ.Env(CSRF_TRUSTED_ORIGINS=(list, []))
        with mock.patch.dict(os.environ, {"CSRF_TRUSTED_ORIGINS": "https://example.com,https://app.railway.app"}):
            origins = env.list("CSRF_TRUSTED_ORIGINS", default=[])
            self.assertEqual(origins, ["https://example.com", "https://app.railway.app"])

    def test_database_url_parsing_mysql(self):
        """Verify DATABASE_URL with MySQL URL parses with correct connection parameters and options."""
        import environ
        env = environ.Env()
        sample_url = "mysql://prod_user:secret_pass@db.railway.internal:3307/railway_prod_db"
        parsed = env.db_url_config(sample_url)

        self.assertEqual(parsed["ENGINE"], "django.db.backends.mysql")
        self.assertEqual(parsed["NAME"], "railway_prod_db")
        self.assertEqual(parsed["USER"], "prod_user")
        self.assertEqual(parsed["PASSWORD"], "secret_pass")
        self.assertEqual(parsed["HOST"], "db.railway.internal")
        self.assertEqual(parsed["PORT"], 3307)

    def test_database_url_precedence_in_base_settings(self):
        """Verify DATABASE_URL takes precedence over DB_* variables when set."""
        fake_env = {
            "SECRET_KEY": "test-secret-key-for-database-url-precedence-validation-32chars",
            "DATABASE_URL": "mysql://railway_usr:railway_pwd@railway_host:3306/railway_db",
            "DB_NAME": "ignored_db",
            "DB_USER": "ignored_user",
            "DB_PASSWORD": "ignored_password",
            "DB_HOST": "127.0.0.1",
            "DB_PORT": "3306",
            "DB_TEST_NAME": "test_custom_db",
            "CONN_MAX_AGE": "120",
            "CONN_HEALTH_CHECKS": "True",
        }
        with mock.patch.dict(os.environ, fake_env, clear=False):
            # Dynamically import base settings under mocked environment
            import config.settings.base as base_mod
            importlib.reload(base_mod)

            db_conf = base_mod.DATABASES["default"]
            self.assertEqual(db_conf["ENGINE"], "django.db.backends.mysql")
            self.assertEqual(db_conf["NAME"], "railway_db")
            self.assertEqual(db_conf["USER"], "railway_usr")
            self.assertEqual(db_conf["PASSWORD"], "railway_pwd")
            self.assertEqual(db_conf["HOST"], "railway_host")
            self.assertEqual(db_conf["PORT"], 3306)
            self.assertEqual(db_conf["OPTIONS"]["charset"], "utf8mb4")
            self.assertIn("STRICT_TRANS_TABLES", db_conf["OPTIONS"]["init_command"])
            self.assertEqual(db_conf["TEST"]["NAME"], "test_custom_db")
            self.assertEqual(db_conf["CONN_MAX_AGE"], 120)
            self.assertTrue(db_conf["CONN_HEALTH_CHECKS"])

        # Reload base settings to restore original state
        importlib.reload(base_mod)

    def test_database_url_unset_falls_back_to_individual_db_vars(self):
        """Verify unsetting DATABASE_URL falls back to DB_* environment variables."""
        fake_env = {
            "SECRET_KEY": "test-secret-key-for-database-fallback-validation-32chars",
            "DATABASE_URL": "",
            "DB_NAME": "fallback_db",
            "DB_USER": "fallback_user",
            "DB_PASSWORD": "fallback_password",
            "DB_HOST": "10.0.0.5",
            "DB_PORT": "3306",
            "DB_TEST_NAME": "test_fallback_db",
            "CONN_MAX_AGE": "90",
            "CONN_HEALTH_CHECKS": "True",
        }
        with mock.patch.dict(os.environ, fake_env, clear=False):
            import config.settings.base as base_mod
            importlib.reload(base_mod)

            db_conf = base_mod.DATABASES["default"]
            self.assertEqual(db_conf["ENGINE"], "django.db.backends.mysql")
            self.assertEqual(db_conf["NAME"], "fallback_db")
            self.assertEqual(db_conf["USER"], "fallback_user")
            self.assertEqual(db_conf["PASSWORD"], "fallback_password")
            self.assertEqual(db_conf["HOST"], "10.0.0.5")
            self.assertEqual(db_conf["PORT"], 3306)
            self.assertEqual(db_conf["OPTIONS"]["charset"], "utf8mb4")
            self.assertEqual(db_conf["TEST"]["NAME"], "test_fallback_db")
            self.assertEqual(db_conf["CONN_MAX_AGE"], 90)
            self.assertTrue(db_conf["CONN_HEALTH_CHECKS"])

        importlib.reload(base_mod)

    def test_production_guard_rejects_sqlite_database_url(self):
        """Verify config.settings.production raises ImproperlyConfigured if DATABASE_URL resolves to SQLite."""
        fake_env = {
            "SECRET_KEY": "a" * 55,
            "ALLOWED_HOSTS": "staging.repairdesk.com",
            "DATABASE_URL": "sqlite:///db.sqlite3",
        }
        with mock.patch.dict(os.environ, fake_env, clear=False):
            import config.settings.base as base_mod
            import config.settings.production as prod_mod
            importlib.reload(base_mod)
            try:
                with self.assertRaises(ImproperlyConfigured) as ctx:
                    importlib.reload(prod_mod)
                self.assertIn("strictly requires MySQL", str(ctx.exception))
            finally:
                # Restore base settings to original environment
                importlib.reload(base_mod)

    def test_production_settings_load_with_valid_mysql_database_url(self):
        """Verify config.settings.production loads successfully when DATABASE_URL is MySQL."""
        fake_env = {
            "SECRET_KEY": "a" * 55,
            "ALLOWED_HOSTS": "staging.repairdesk.com",
            "CSRF_TRUSTED_ORIGINS": "https://staging.repairdesk.com",
            "DATABASE_URL": "mysql://valid_user:valid_pass@valid_host:3306/valid_db",
        }
        with mock.patch.dict(os.environ, fake_env, clear=False):
            import config.settings.base as base_mod
            import config.settings.production as prod_mod
            importlib.reload(base_mod)
            try:
                reloaded = importlib.reload(prod_mod)
                self.assertFalse(reloaded.DEBUG)
                self.assertTrue(reloaded.SESSION_COOKIE_SECURE)
                self.assertTrue(reloaded.CSRF_COOKIE_SECURE)
                self.assertTrue(reloaded.SECURE_SSL_REDIRECT)
                self.assertEqual(reloaded.DATABASES["default"]["ENGINE"], "django.db.backends.mysql")
            finally:
                importlib.reload(base_mod)
