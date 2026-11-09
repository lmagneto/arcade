
import json
import getpass
import urllib.request
import urllib.error

url = "http://127.0.0.1:8000/api/devices/activation-requests/"
account_id = "5ce9f54e-3677-493c-8ff4-ded78aa64892"

token = getpass.getpass("Paste administrator ACCESS token: ")

payload = {"major_account_id": account_id}
request = urllib.request.Request(
    url,
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    },
    method="POST",
)

try:
    with urllib.request.urlopen(request) as response:
        result = json.loads(response.read().decode("utf-8"))
        print("HTTP:", response.status)
        print("Installation ID:", result["installation_id"])
        print("Activation code:", result["activation_code"])
        print("Expires at:", result["expires_at"])
        print("\nSave the installation ID and activation code privately.")
except urllib.error.HTTPError as error:
    print("HTTP:", error.code)
    print("Error:", error.read().decode("utf-8"))

