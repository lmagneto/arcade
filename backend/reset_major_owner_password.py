
import getpass
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from accounts.models import User

username = input("Major owner username [test_major_owner]: ").strip()
if not username:
    username = "test_major_owner"

try:
    user = User.objects.get(username=username)
except User.DoesNotExist:
    raise SystemExit("That username does not exist. No changes made.")

if user.role != User.Role.MAJOR_OWNER:
    raise SystemExit(
        f"User role is {user.role}, not MAJOR_OWNER. No changes made."
    )

password = getpass.getpass("Enter a new password: ")
confirmation = getpass.getpass("Confirm new password: ")

if len(password) < 12:
    raise SystemExit("Use a password with at least 12 characters.")

if password != confirmation:
    raise SystemExit("Passwords do not match. No changes made.")

user.set_password(password)
user.save(update_fields=["password"])

print(f"Password reset successfully for {user.username}.")
print("The existing account and player slots were not changed.")
