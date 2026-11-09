
import os
import getpass
import uuid
from decimal import Decimal

import django
import requests

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from tenants.models import MajorAccount
from wallets.models import Wallet

BASE_URL = "http://127.0.0.1:8000"
USERNAME = "lewy"
MAJOR_ACCOUNT_ID = "5ce9f54e-3677-493c-8ff4-ded78aa64892"
AMOUNT = "600.00"


def main():
    password = getpass.getpass("Platform administrator password: ")

    login_response = requests.post(
        f"{BASE_URL}/api/token/",
        json={"username": USERNAME, "password": password},
        timeout=15,
    )

    if login_response.status_code != 200:
        print("Login failed. HTTP status:", login_response.status_code)
        print("Response:", login_response.text)
        return

    headers = {
        "Authorization": f"Bearer {login_response.json()['access']}"
    }
    print("Login successful.")

    account = MajorAccount.objects.get(id=MAJOR_ACCOUNT_ID)
    reserve_before = Wallet.objects.get(
        platform_reserve=True
    ).available_balance
    major_before = Wallet.objects.get(
        major_account=account
    ).available_balance

    print("Reserve balance before:", reserve_before)
    print("Major account balance before:", major_before)

    response = requests.post(
        f"{BASE_URL}/api/wallets/platform/allocate/",
        headers=headers,
        json={
            "major_account_id": MAJOR_ACCOUNT_ID,
            "amount": AMOUNT,
            "idempotency_key": str(uuid.uuid4()),
            "description": "Test allocation to Test Major Account",
        },
        timeout=15,
    )

    print("Allocation HTTP status:", response.status_code)
    print("Response:", response.text)

    reserve_after = Wallet.objects.get(
        platform_reserve=True
    ).available_balance
    major_after = Wallet.objects.get(
        major_account=account
    ).available_balance

    print("Reserve balance after:", reserve_after)
    print("Major account balance after:", major_after)

    if response.status_code == 201:
        expected_reserve = reserve_before - Decimal(AMOUNT)
        expected_major = major_before + Decimal(AMOUNT)

        if (
            reserve_after == expected_reserve
            and major_after == expected_major
        ):
            print("PASS: allocation balances are correct.")
        else:
            print("CHECK: successful response, but balances differ.")
    else:
        print("Allocation failed. Do not retry until the result is checked.")


if __name__ == "__main__":
    main()
