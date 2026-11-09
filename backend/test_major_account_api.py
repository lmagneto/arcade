
import getpass
import json
import urllib.error
import urllib.request

BASE_URL = "http://127.0.0.1:8000"

username = input("Major account username: ").strip()
password = getpass.getpass("Password: ")

def request_json(path, method="GET", data=None, token=None):
    body = None
    headers = {"Accept": "application/json"}

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
            payload = json.loads(exc.read())
        except Exception:
            payload = {"detail": str(exc)}
        return exc.code, payload
    except urllib.error.URLError as exc:
        return 0, {"detail": str(exc.reason)}

status_code, result = request_json(
    "/api/token/",
    method="POST",
    data={"username": username, "password": password},
)

print(f"\nLogin HTTP status: {status_code}")

if status_code != 200:
    print(result)
    raise SystemExit("Login failed. Check the username and password.")

access_token = result["access"]

status_code, accounts = request_json(
    "/api/wallets/major-accounts/",
    token=access_token,
)

print(f"\nMajor accounts HTTP status: {status_code}")
print(json.dumps(accounts, indent=2))

if status_code == 200 and accounts.get("accounts"):
    account_id = accounts["accounts"][0]["id"]

    status_code, players = request_json(
        f"/api/wallets/major-accounts/{account_id}/players/",
        token=access_token,
    )

    print(f"\nPlayer slots HTTP status: {status_code}")
    print(json.dumps(players, indent=2))
