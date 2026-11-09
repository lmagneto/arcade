
import getpass
import os
import uuid
from decimal import Decimal

import requests

BASE_URL = "http://127.0.0.1:8000"
USERNAME = "lewy"
AMOUNT = "1000.00"

password = getpass.getpass("Platform administrator password: ")

login_response = requests.post(
    f"{BASE_URL}/api/token/",
    json={
        "username": USERNAME,
        "password": password,
    },
    timeout=15,
)

if login_response.status_code != 200:
    print("Login failed. HTTP status:", login_response.status_code)
    print("Response:", login_response.text)
    raise SystemExit(1)

access_token = login_response.json()["access"]
headers = {"Authorization": f"Bearer {access_token}"}

print("Login successful.")

# Read the reserve balance directly from the database.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from wallets.models import Wallet

before = Wallet.objects.get(platform_reserve=True).available_balance
print("Reserve balance before:", before)

response = requests.post(
    f"{BASE_URL}/api/wallets/platform/issue/",
    headers=headers,
    json={
        "amount": AMOUNT,
        "idempotency_key": str(uuid.uuid4()),
        "description": "Test virtual-credit issuance",
    },
    timeout=15,
)

print("Issuance HTTP status:", response.status_code)
print("Response:", response.text)

after = Wallet.objects.get(platform_reserve=True).available_balance
print("Reserve balance after:", after)

if response.status_code == 201:
    expected = before + Decimal(AMOUNT)
    if after == expected:
        print("PASS: reserve balance increased correctly.")
    else:
        print("CHECK: response succeeded but balance differs from expectation.")
else:
    print("Issuance was not successful; investigate the response above.")
