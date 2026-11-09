
import os
import django
from getpass import getpass

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.test import Client, override_settings

with override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"]):
    client = Client()
    password = getpass("Test account password: ")

    login = client.post(
        "/api/token/",
        {"username": "test_major_owner", "password": password},
        content_type="application/json",
    )

    print("LOGIN:", login.status_code)

    if login.status_code != 200:
        print("Login response:", login.content.decode()[:300])
    else:
        import json
        data = json.loads(login.content)
        print("Must change password:", data.get("must_change_password"))

        headers = {"HTTP_AUTHORIZATION": "Bearer " + data["access"]}

        protected = client.get(
            "/api/wallets/major-accounts/",
            **headers,
        )
        print("PROTECTED ENDPOINT:", protected.status_code)

        change = client.post(
            "/api/accounts/change-password/",
            data="{}",
            content_type="application/json",
            **headers,
        )
        print("PASSWORD-CHANGE ENDPOINT:", change.status_code)
