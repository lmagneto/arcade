import os
from io import StringIO
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import TestCase

from accounts.models import User


class BootstrapAdminCommandTests(TestCase):
    environment = {
        "BOOTSTRAP_ADMIN_USERNAME": "bootstrap-test-admin",
        "BOOTSTRAP_ADMIN_EMAIL": "admin@example.com",
        "BOOTSTRAP_ADMIN_PASSWORD": "A-Long-Initial-Password-8472!",
    }

    def call_bootstrap(self, environment=None):
        configured_environment = (
            self.environment if environment is None else environment
        )
        with patch.dict(os.environ, configured_environment):
            output = StringIO()
            call_command("bootstrap_admin", stdout=output)
        return output.getvalue()

    def test_skips_when_no_bootstrap_values_are_configured(self):
        empty_environment = dict.fromkeys(self.environment, "")

        output = self.call_bootstrap(empty_environment)

        self.assertIn("skipped", output)
        self.assertFalse(User.objects.exists())

    def test_creates_platform_superuser_and_requires_password_change(self):
        output = self.call_bootstrap()
        user = User.objects.get(username="bootstrap-test-admin")
        password = self.environment["BOOTSTRAP_ADMIN_PASSWORD"]

        self.assertIn("created successfully", output)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)
        self.assertEqual(user.role, User.Role.PLATFORM_ADMIN)
        self.assertTrue(user.must_change_password)
        self.assertTrue(user.check_password(password))
        self.assertNotIn(password, output)

    def test_existing_admin_is_not_modified_or_reset(self):
        self.call_bootstrap()
        user = User.objects.get(username="bootstrap-test-admin")
        original_password = self.environment["BOOTSTRAP_ADMIN_PASSWORD"]
        user.set_password(original_password)
        user.save(update_fields=["password"])

        changed_environment = {
            **self.environment,
            "BOOTSTRAP_ADMIN_PASSWORD": "A-Different-Password-9201!",
        }
        output = self.call_bootstrap(changed_environment)

        user.refresh_from_db()
        self.assertIn("already exists", output)
        self.assertTrue(user.check_password(original_password))
        self.assertFalse(user.check_password(
            changed_environment["BOOTSTRAP_ADMIN_PASSWORD"]
        ))

    def test_existing_non_admin_username_is_not_promoted(self):
        User.objects.create_user(
            username="bootstrap-test-admin",
            email="admin@example.com",
            password="Regular-user-password-8421!",
        )

        with self.assertRaises(CommandError):
            self.call_bootstrap()

        user = User.objects.get(username="bootstrap-test-admin")
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_staff)

    def test_partial_environment_configuration_fails(self):
        partial_environment = {
            **self.environment,
            "BOOTSTRAP_ADMIN_PASSWORD": "",
        }

        with self.assertRaises(CommandError):
            self.call_bootstrap(partial_environment)
