
import json
import urllib.request
import urllib.error
from pathlib import Path

credential_file = Path(__file__).with_name("device_credential.txt")
credential = credential_file.read_text(encoding="utf-8").strip()

request = urllib.request.Request(
    "http://127.0.0.1:8000/api/devices/status/",
    headers={"Authorization": f"Device {credential}"},
    method="GET",
)

try:
    with urllib.request.urlopen(request) as response:
        result = json.loads(response.read().decode("utf-8"))
        print("HTTP:", response.status)
        print("Device authentication successful.")
        print(json.dumps(result, indent=2))
except urllib.error.HTTPError as error:
    print("HTTP:", error.code)
    print("Response:", error.read().decode("utf-8"))
finally:
    credential = None
