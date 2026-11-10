import os

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import transaction

from accounts.models import User


ENVIRONMENT_KEYS = (
    "BOOTSTRAP_ADMIN_USERNAME",
    "BOOTSTRAP_ADMIN_EMAIL",
    "BOOTSTRAP_ADMIN_PASSWORD",
)


class Command(BaseCommand):
    help = "Create the initial platform administrator from environment secrets."

    @transaction.atomic
    def handle(self, *args, **options):
        username = os.environ.get(ENVIRONMENT_KEYS[0], "").strip()
        email = os.environ.get(ENVIRONMENT_KEYS[1], "").strip()
        password = os.environ.get(ENVIRONMENT_KEYS[2], "")

        if not any((username, email, password)):
            self.stdout.write("Admin bootstrap is not configured; skipped.")
            return

        if not all((username, email, password)):
            raise CommandError(
                "Set all BOOTSTRAP_ADMIN_USERNAME, "
                "BOOTSTRAP_ADMIN_EMAIL, and BOOTSTRAP_ADMIN_PASSWORD "
                "environment variables."
            )

        existing = User.objects.filter(username=username).first()
        if existing is not None:
            if (
                existing.is_superuser
                and existing.is_staff
                and existing.role == User.Role.PLATFORM_ADMIN
            ):
                self.stdout.write(
                    "Platform administrator already exists; no changes made."
                )
                return

            raise CommandError(
                "The configured username belongs to a non-admin account; "
                "no changes were made."
            )

        try:
            username_field = User._meta.get_field("username")
            if len(username) > username_field.max_length:
                raise ValidationError("Username is too long.")

            for validator in username_field.validators:
                validator(username)

            validate_email(email)
            validate_password(
                password,
                user=User(username=username, email=email),
            )
        except ValidationError as exc:
            raise CommandError(
                "The configured username, email, or password does not meet "
                "the account validation requirements."
            ) from exc

        User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
            role=User.Role.PLATFORM_ADMIN,
            must_change_password=True,
        )
        self.stdout.write(
            self.style.SUCCESS("Platform administrator created successfully.")
        )
