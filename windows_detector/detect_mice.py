
import json
import subprocess
import time


CHECK_INTERVAL_SECONDS = 2


def detect_external_mice():
    command = [
        "powershell",
        "-NoProfile",
        "-Command",
        (
            "Get-PnpDevice -Class Mouse -PresentOnly | "
            "Select-Object Status, FriendlyName, InstanceId | "
            "ConvertTo-Json -Compress"
        ),
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )

    if not result.stdout.strip():
        return []

    devices = json.loads(result.stdout)

    if isinstance(devices, dict):
        devices = [devices]

    return [
        device
        for device in devices
        if device.get("Status") == "OK"
        and device.get("InstanceId", "").upper().startswith("HID\\")
        and "TOUCHPAD" not in device.get("FriendlyName", "").upper()
    ]


def monitor_mice():
    previous_ids = None

    print("Windows mouse detector started.")
    print("Press Ctrl+C to stop.")

    try:
        while True:
            try:
                mice = detect_external_mice()
                current_ids = tuple(sorted(
                    mouse["InstanceId"] for mouse in mice
                ))

                if current_ids != previous_ids:
                    print(
                        f"Detected external mouse devices: {len(mice)}"
                    )
                    previous_ids = current_ids

            except (subprocess.SubprocessError, OSError, ValueError) as exc:
                print(f"Detection error: {exc}")

            time.sleep(CHECK_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\nMouse detector stopped.")


if __name__ == "__main__":
    monitor_mice()
