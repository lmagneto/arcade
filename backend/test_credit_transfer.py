
import getpass
import json
import urllib.error
import urllib.request
import uuid

BASE_URL = "http://127.0.0.1:8000"

username = input("Major owner username: ").strip()
password = getpass.getpass("Password: ")

def request_json(path, method="GET", data=None, token=None):
    headers = {"Accept": "application/json"}
    body = None

    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"

    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(
        BASE_URL + path,
        data=body,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        try:
            result = json.loads(exc.read())
        except Exception:
            result = {"detail": str(exc)}
        return exc.code, result
    except urllib.error.URLError as exc:
        return 0, {"detail": str(exc.reason)}

status_code, login = request_json(
    "/api/token/",
    method="POST",
    data={"username": username, "password": password},
)

if status_code != 200:
    print("Login failed:", status_code, login)
    raise SystemExit(1)

token = login["access"]

status_code, account_data = request_json(
    "/api/wallets/major-accounts/",
    token=token,
)

if status_code != 200 or not account_data.get("accounts"):
    print("Could not retrieve major account:", status_code, account_data)
    raise SystemExit(1)

account = account_data["accounts"][0]

status_code, player_data = request_json(
    f"/api/wallets/major-accounts/{account['id']}/players/",
    token=token,
)

if status_code != 200 or not player_data.get("players"):
    print("Could not retrieve player slots:", status_code, player_data)
    raise SystemExit(1)

player = player_data["players"][0]

print("\nTesting account:", account["name"])
print("Major wallet before:", account["wallet_balance"])
print("Player before:", player["display_name"], player["wallet_balance"])

status_code, result = request_json(
    f"/api/wallets/major-accounts/{account['id']}/players/{player['id']}/transfer/",
    method="POST",
    token=token,
    data={
        "direction": "CREDIT",
        "amount": "1.00",
        "idempotency_key": str(uuid.uuid4()),
    },
)

print("\nTransfer HTTP status:", status_code)
print(json.dumps(result, indent=2))

if status_code == 409:
    print("\nInsufficient-balance protection responded as expected.")
elif status_code == 200:
    print("\nA transfer succeeded; verify both balances and ledger entries.")
else:
    print("\nUnexpected result. Review the response above.")
