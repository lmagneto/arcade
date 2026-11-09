
import getpass
import json
import urllib.request
import urllib.error
from pathlib import Path

url = "http://127.0.0.1:8000/api/devices/activate/"

installation_id = input("Enter the NEW installation ID: ").strip()
activation_code = getpass.getpass("Enter the NEW activation code: ")

payload = {
    "installation_id": installation_id,
    "activation_code": activation_code,
    "device_name": "Test Windows PC",
}

request = urllib.request.Request(
    url,
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)

try:
    with urllib.request.urlopen(request) as response:
        result = json.loads(response.read().decode("utf-8"))

        print("HTTP:", response.status)
        print("Installation activated successfully.")
        print("Status:", result.get("status"))

        credential = result.get("device_credential")
        if not credential:
            print("ERROR: No device credential returned.")
        else:
            credential_file = Path("device_credential.txt")
            credential_file.write_text(credential, encoding="utf-8")
            print("Device credential saved locally.")
            print("File:", credential_file.resolve())

except urllib.error.HTTPError as error:
    print("HTTP:", error.code)
    print("Error:", error.read().decode("utf-8"))
