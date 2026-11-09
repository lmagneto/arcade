
import getpass

import django

django.setup()

from accounts.models import User

username = "lewy"

user = User.objects.get(username=username)

new_password = getpass.getpass("Enter a new administrator password: ")
confirm_password = getpass.getpass("Confirm the new password: ")

if new_password != confirm_password:
    print("Passwords do not match. No changes made.")
    raise SystemExit(1)

if len(new_password) < 12:
    print("Use a password of at least 12 characters. No changes made.")
    raise SystemExit(1)

user.set_password(new_password)
user.is_active = True
user.is_staff = True
user.save(update_fields=["password", "is_active", "is_staff"])

print("Administrator password updated successfully.")
