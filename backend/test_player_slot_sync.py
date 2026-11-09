
import json
import urllib.request
import urllib.error
from pathlib import Path

credential_path = Path(__file__).with_name("device_credential.txt")
credential = credential_path.read_text(encoding="utf-8").strip()

payload = {"detected_count": 1}

request = urllib.request.Request(
    "http://127.0.0.1:8000/api/devices/player-slots/sync/",
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "Content-Type": "application/json",
        "Authorization": f"Device {credential}",
    },
    method="POST",
)

try:
    with urllib.request.urlopen(request) as response:
        result = json.loads(response.read().decode("utf-8"))
        print("HTTP:", response.status)
        print("Player-slot synchronization successful.")
        print(json.dumps(result, indent=2))
except urllib.error.HTTPError as error:
    print("HTTP:", error.code)
    print("Response:", error.read().decode("utf-8"))
