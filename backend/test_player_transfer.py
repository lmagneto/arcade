
import os
import getpass
import uuid
from decimal import Decimal

import django
import requests

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from tenants.models import MajorAccount, PlayerSlot
from wallets.models import Wallet, LedgerTransaction, LedgerEntry

BASE_URL = "http://127.0.0.1:8000"
USERNAME = "test_major_owner"
MAJOR_ACCOUNT_ID = "5ce9f54e-3677-493c-8ff4-ded78aa64892"
PLAYER_SLOT_ID = "5ad5afcb-4258-40fe-b966-4acc0a2acb56"
AMOUNT = "100.00"


def main():
    password = getpass.getpass("Major account owner password: ")

    login_response = requests.post(
        f"{BASE_URL}/api/token/",
        json={"username": USERNAME, "password": password},
        timeout=15,
    )

    if login_response.status_code != 200:
        print("Login failed:", login_response.status_code)
        print("Response:", login_response.text)
        return

    headers = {
        "Authorization": f"Bearer {login_response.json()['access']}"
    }
    print("Login successful.")

    account = MajorAccount.objects.get(id=MAJOR_ACCOUNT_ID)
    player = PlayerSlot.objects.get(
        id=PLAYER_SLOT_ID,
        major_account=account,
    )

    major_wallet = Wallet.objects.get(major_account=account)
    player_wallet = Wallet.objects.get(player_slot=player)

    major_before = major_wallet.available_balance
    player_before = player_wallet.available_balance

    print("Major account balance before:", major_before)
    print("Player 1 balance before:", player_before)

    response = requests.post(
        f"{BASE_URL}/api/wallets/major-accounts/"
        f"{MAJOR_ACCOUNT_ID}/players/{PLAYER_SLOT_ID}/transfer/",
        headers=headers,
        json={
            "direction": "CREDIT",
            "amount": AMOUNT,
            "idempotency_key": str(uuid.uuid4()),
        },
        timeout=15,
    )

    print("Transfer HTTP status:", response.status_code)
    print("Response:", response.text)

    major_after = Wallet.objects.get(
        major_account=account
    ).available_balance
    player_after = Wallet.objects.get(
        player_slot=player
    ).available_balance

    print("Major account balance after:", major_after)
    print("Player 1 balance after:", player_after)

    if response.status_code != 200:
        print("Transfer failed. Do not retry until checked.")
        return

    expected_major = major_before - Decimal(AMOUNT)
    expected_player = player_before + Decimal(AMOUNT)

    if major_after != expected_major or player_after != expected_player:
        print("CHECK: balances differ from expectations.")
        return

    reference = response.json().get("reference")
    ledger_transaction = LedgerTransaction.objects.get(
        reference=reference
    )
    entries = list(
        LedgerEntry.objects.filter(
            transaction=ledger_transaction
        ).values("wallet_id", "direction", "amount")
    )

    print("Ledger entries:", entries)

    debits = [
        entry for entry in entries
        if entry["direction"] == "DEBIT"
    ]
    credits = [
        entry for entry in entries
        if entry["direction"] == "CREDIT"
    ]

    if (
        len(entries) == 2
        and len(debits) == 1
        and len(credits) == 1
        and debits[0]["amount"] == credits[0]["amount"]
        and debits[0]["amount"] == Decimal(AMOUNT)
    ):
        print("PASS: balances and double-entry ledger are correct.")
    else:
        print("CHECK: ledger entries do not match the expected transfer.")


if __name__ == "__main__":
    main()
