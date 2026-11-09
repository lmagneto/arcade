
import json
import urllib.request
import urllib.error
from pathlib import Path

credential = Path(__file__).with_name(
    "device_credential.txt"
).read_text(encoding="utf-8").strip()

url = "http://127.0.0.1:8000/api/devices/player-slots/sync/"

test_cases = [
    ("zero", {"detected_count": 0}),
    ("nine", {"detected_count": 9}),
    ("string", {"detected_count": "3"}),
    ("boolean", {"detected_count": True}),
]

for label, payload in test_cases:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Device {credential}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request) as response:
            print(label, "HTTP", response.status, "(unexpected success)")
    except urllib.error.HTTPError as error:
        print(label, "HTTP", error.code)
        print(error.read().decode("utf-8"))

print("Validation test completed.")

