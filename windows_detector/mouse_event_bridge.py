
"""ARCADE Windows Raw Input mouse-event bridge.

Run from the project root:
    venv\Scripts\python.exe windows_detector\mouse_event_bridge.py

Endpoints:
    GET /health
    GET /devices
    GET /events?since=0

Player slots are assigned by first mouse activity for this session.
This is a local development bridge, not a production security boundary.
"""

import ctypes
import json
import threading
import time
from collections import deque
from ctypes import wintypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import win32api
import win32con
import win32gui


# Windows Raw Input constants
WM_INPUT = 0x00FF
WM_INPUT_DEVICE_CHANGE = 0x00FE
WM_CLOSE = 0x0010
WM_DESTROY = 0x0002

GIDC_ARRIVAL = 1
GIDC_REMOVAL = 2

RID_INPUT = 0x10000003
RIDI_DEVICENAME = 0x20000007
RIM_TYPEMOUSE = 0
RIDEV_INPUTSINK = 0x00000100
RIDEV_DEVNOTIFY = 0x00002000

# Mouse button flags
BUTTON_EVENTS = (
    (0x0001, "LEFT_DOWN"),
    (0x0002, "LEFT_UP"),
    (0x0004, "RIGHT_DOWN"),
    (0x0008, "RIGHT_UP"),
    (0x0010, "MIDDLE_DOWN"),
    (0x0020, "MIDDLE_UP"),
    (0x0040, "BUTTON4_DOWN"),
    (0x0080, "BUTTON4_UP"),
    (0x0100, "BUTTON5_DOWN"),
    (0x0200, "BUTTON5_UP"),
    (0x0400, "WHEEL"),
    (0x0800, "HORIZONTAL_WHEEL"),
)

user32 = ctypes.WinDLL("user32", use_last_error=True)

user32.GetRawInputData.argtypes = [
    wintypes.HANDLE,
    wintypes.UINT,
    ctypes.c_void_p,
    ctypes.POINTER(wintypes.UINT),
    wintypes.UINT,
]
user32.GetRawInputData.restype = wintypes.UINT

user32.GetRawInputDeviceInfoW.argtypes = [
    wintypes.HANDLE,
    wintypes.UINT,
    ctypes.c_void_p,
    ctypes.POINTER(wintypes.UINT),
]
user32.GetRawInputDeviceInfoW.restype = wintypes.UINT

user32.RegisterRawInputDevices.argtypes = [
    ctypes.c_void_p,
    wintypes.UINT,
    wintypes.UINT,
]
user32.RegisterRawInputDevices.restype = wintypes.BOOL

user32.DefWindowProcW.argtypes = [
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
]
user32.DefWindowProcW.restype = ctypes.c_ssize_t


class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ("usUsagePage", wintypes.USHORT),
        ("usUsage", wintypes.USHORT),
        ("dwFlags", wintypes.DWORD),
        ("hwndTarget", wintypes.HWND),
    ]


class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [
        ("dwType", wintypes.DWORD),
        ("dwSize", wintypes.DWORD),
        ("hDevice", wintypes.HANDLE),
        ("wParam", wintypes.WPARAM),
    ]


class RAWMOUSE_BUTTONS(ctypes.Structure):
    _fields_ = [
        ("usButtonFlags", wintypes.USHORT),
        ("usButtonData", wintypes.USHORT),
    ]


class RAWMOUSE_BUTTON_UNION(ctypes.Union):
    _fields_ = [
        ("ulButtons", wintypes.ULONG),
        ("button_data", RAWMOUSE_BUTTONS),
    ]


class RAWMOUSE(ctypes.Structure):
    _anonymous_ = ("buttons",)
    _fields_ = [
        ("usFlags", wintypes.USHORT),
        ("buttons", RAWMOUSE_BUTTON_UNION),
        ("ulRawButtons", wintypes.ULONG),
        ("lLastX", wintypes.LONG),
        ("lLastY", wintypes.LONG),
        ("ulExtraInformation", wintypes.ULONG),
    ]


class RAWINPUT(ctypes.Structure):
    _fields_ = [
        ("header", RAWINPUTHEADER),
        ("mouse", RAWMOUSE),
    ]


if ctypes.sizeof(RAWMOUSE) != 24:
    raise RuntimeError(
        f"Unexpected RAWMOUSE size: {ctypes.sizeof(RAWMOUSE)}"
    )


# Shared bridge state
state_lock = threading.Lock()
device_names = {}
device_slots = {}
last_activity = {}
event_buffer = deque(maxlen=2000)
next_event_id = 1
started_at = time.time()


def handle_value(handle):
    """Convert a Windows handle to an integer for JSON output."""
    if handle is None:
        return 0
    try:
        return int(handle)
    except (TypeError, ValueError):
        value = ctypes.cast(handle, ctypes.c_void_p).value
        return int(value or 0)


def get_device_name(handle):
    """Get and cache the Windows device path."""
    key = handle_value(handle)

    if key in device_names:
        return device_names[key]

    char_count = wintypes.UINT(0)

    result = user32.GetRawInputDeviceInfoW(
        handle,
        RIDI_DEVICENAME,
        None,
        ctypes.byref(char_count),
    )

    if result == 0xFFFFFFFF or char_count.value == 0:
        name = f"Unknown device ({key})"
    else:
        buffer = ctypes.create_unicode_buffer(char_count.value + 1)

        result = user32.GetRawInputDeviceInfoW(
            handle,
            RIDI_DEVICENAME,
            ctypes.cast(buffer, ctypes.c_void_p),
            ctypes.byref(char_count),
        )

        if result == 0xFFFFFFFF:
            name = f"Unknown device ({key})"
        else:
            name = buffer.value or f"Unnamed device ({key})"

    device_names[key] = name
    return name


def read_raw_input(raw_handle):
    """Read one RAWINPUT structure from Windows."""
    header_size = ctypes.sizeof(RAWINPUTHEADER)
    required_size = wintypes.UINT(0)

    result = user32.GetRawInputData(
        raw_handle,
        RID_INPUT,
        None,
        ctypes.byref(required_size),
        header_size,
    )

    if result == 0xFFFFFFFF or required_size.value < header_size:
        return None

    buffer = ctypes.create_string_buffer(required_size.value)

    bytes_read = user32.GetRawInputData(
        raw_handle,
        RID_INPUT,
        ctypes.cast(buffer, ctypes.c_void_p),
        ctypes.byref(required_size),
        header_size,
    )

    if bytes_read == 0xFFFFFFFF:
        return None

    if bytes_read < ctypes.sizeof(RAWINPUT):
        return None

    return RAWINPUT.from_buffer_copy(buffer.raw[:bytes_read])



def register_device(handle):
    """Register an eligible mouse and assign the next available slot."""

    key = handle_value(handle)

    if key <= 0:
        return None

    name = get_device_name(handle)
    normalized_name = name.upper()

    if normalized_name.startswith(r"\\?\ACPI#"):
        return None

    if (
        normalized_name.startswith("UNKNOWN DEVICE")
        or normalized_name.startswith("UNNAMED DEVICE")
    ):
        return None

    with state_lock:

        # Reuse an existing slot if Windows reports the same
        # physical device under a new handle after reconnection.
        for old_key, old_name in list(device_names.items()):
            if (
                old_name.upper() == normalized_name
                and old_key in device_slots
                and old_key != key
            ):
                slot = device_slots.pop(old_key)
                last_activity.pop(old_key, None)

                device_slots[key] = slot
                device_names[key] = name
                last_activity[key] = time.time()

                print(
                    f"Mouse reconnected: Player {slot} | {name}",
                    flush=True,
                )

                return slot

        if key not in device_slots:
            if len(device_slots) >= 8:
                return None

            used_slots = set(device_slots.values())

            slot = next(
                (
                    number
                    for number in range(1, 9)
                    if number not in used_slots
                ),
                None,
            )

            if slot is None:
                return None

            device_slots[key] = slot

        last_activity[key] = time.time()

        return device_slots[key]


def remove_device(handle):
    """Remove a disconnected physical mouse and compact player slots."""

    key = handle_value(handle)

    if key <= 0:
        return

    with state_lock:

        slot = device_slots.pop(key, None)

        device_names.pop(key, None)
        last_activity.pop(key, None)

        if slot is None:
            return

        # Keep remaining players in sequential slot order.
        remaining = sorted(
            device_slots.items(),
            key=lambda item: item[1],
        )

        for new_slot, (device_key, old_slot) in enumerate(
            remaining, start=1
        ):
            device_slots[device_key] = new_slot

        print(
            f"Mouse disconnected: Player {slot}. "
            f"Remaining mice: {len(device_slots)}",
            flush=True,
        )



def record_button_events(handle, flags, button_data):
    """Record button events with their assigned player slot."""
    global next_event_id

    key = handle_value(handle)
    slot = register_device(handle)

    if slot is None:
        print(
            f"Ignoring device handle {key}: maximum of 8 devices reached.",
            flush=True,
        )
        return

    name = get_device_name(handle)

    for flag, label in BUTTON_EVENTS:
        if not flags & flag:
            continue

        event = {
            "id": None,
            "player_slot": slot,
            "device_handle": key,
            "device_name": name,
            "button": label,
            "timestamp": time.time(),
        }

        if label in ("WHEEL", "HORIZONTAL_WHEEL"):
            event["wheel_delta"] = ctypes.c_short(button_data).value

        with state_lock:
            event["id"] = next_event_id
            event_buffer.append(event)
            next_event_id += 1

        print(
            f"Player {slot} | {label} | handle {key} | {name}",
            flush=True,
        )


def window_proc(hwnd, msg, wparam, lparam):
    """Receive Raw Input from Windows."""
    if msg == WM_INPUT_DEVICE_CHANGE:
        if wparam == GIDC_REMOVAL:
            remove_device(lparam)

        elif wparam == GIDC_ARRIVAL:
            print(
                "Mouse connected. Waiting for first activity.",
                flush=True,
            )

        return 0
    if msg == WM_INPUT:
        try:
            raw = read_raw_input(wintypes.HANDLE(lparam))

            if raw is not None and raw.header.dwType == RIM_TYPEMOUSE:
                slot = register_device(raw.header.hDevice)

                if slot is not None:
                    flags = raw.mouse.buttons.button_data.usButtonFlags

                    if flags:
                        record_button_events(
                            raw.header.hDevice,
                            flags,
                            raw.mouse.buttons.button_data.usButtonData,
                        )

        except Exception as exc:
            print(f"Raw Input error: {exc!r}", flush=True)

        finally:
            # Windows requires default processing of WM_INPUT.
            user32.DefWindowProcW(
                wintypes.HWND(hwnd),
                wintypes.UINT(msg),
                wintypes.WPARAM(wparam),
                wintypes.LPARAM(lparam),
            )

        return 0

    if msg == WM_CLOSE:
        win32gui.DestroyWindow(hwnd)
        return 0

    if msg == WM_DESTROY:
        win32gui.PostQuitMessage(0)
        return 0

    return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)


class BridgeHandler(BaseHTTPRequestHandler):
    """Local HTTP API for the React development frontend."""

    def send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")

        self.send_response(status)
        self.send_header(
            "Content-Type", "application/json; charset=utf-8"
        )
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/health":
            self.send_json({
                "status": "ok",
                "service": "arcade-mouse-event-bridge",
                "uptime_seconds": round(time.time() - started_at, 1),
            })
            return

        if parsed.path == "/devices":
            with state_lock:
                devices = [
                    {
                        "player_slot": slot,
                        "device_handle": key,
                        "device_name": device_names.get(
                            key, "Name pending"
                        ),
                        "last_activity": last_activity.get(key),
                    }
                    for key, slot in sorted(
                        device_slots.items(),
                        key=lambda item: item[1],
                    )
                ]

            self.send_json({
                "count": len(devices),
                "devices": devices,
            })
            return

        if parsed.path == "/events":
            try:
                query = parse_qs(parsed.query)
                since = int(query.get("since", ["0"])[0])
                if since < 0:
                    raise ValueError
            except ValueError:
                self.send_json({
                    "error": "since must be a non-negative integer"
                }, 400)
                return

            with state_lock:
                events = [
                    event for event in event_buffer
                    if event["id"] > since
                ]
                latest_id = next_event_id - 1

            self.send_json({
                "events": events,
                "latest_id": latest_id,
            })
            return

        self.send_json({
            "error": "Not found",
            "endpoints": [
                "/health",
                "/devices",
                "/events?since=0",
            ],
        }, 404)

    def log_message(self, fmt, *args):
        # Avoid logging every polling request.
        if urlparse(self.path).path != "/health":
            super().log_message(fmt, *args)


def run_http_server():
    server = ThreadingHTTPServer(
        ("127.0.0.1", 8765),
        BridgeHandler,
    )
    print(
        "HTTP bridge listening at http://127.0.0.1:8765",
        flush=True,
    )

    try:
        server.serve_forever()
    finally:
        server.server_close()


def main():
    http_thread = threading.Thread(
        target=run_http_server,
        daemon=True,
    )
    http_thread.start()

    class_name = "ArcadeRawMouseBridge"
    instance = win32api.GetModuleHandle(None)

    window_class = win32gui.WNDCLASS()
    window_class.hInstance = instance
    window_class.lpszClassName = class_name
    window_class.lpfnWndProc = window_proc

    try:
        win32gui.RegisterClass(window_class)
    except win32gui.error:
        pass

    hwnd = win32gui.CreateWindow(
        class_name,
        "ARCADE Mouse Event Bridge - close window to stop",
        win32con.WS_OVERLAPPEDWINDOW,
        100,
        100,
        680,
        180,
        0,
        0,
        instance,
        None,
    )

    raw_device = RAWINPUTDEVICE(
        0x01,
        0x02,
        RIDEV_INPUTSINK | RIDEV_DEVNOTIFY,
        hwnd,
    )

  
    if not user32.RegisterRawInputDevices(
        ctypes.byref(raw_device),
        1,
        ctypes.sizeof(RAWINPUTDEVICE),
    ):
        error_code = ctypes.get_last_error()
        win32gui.DestroyWindow(hwnd)
        raise ctypes.WinError(error_code)

    print("ARCADE mouse-event bridge is running.", flush=True)
    print("Move each physical mouse once to register it.", flush=True)
    print("Player slots are assigned by first activity.", flush=True)
    print("Maximum supported devices: 8.", flush=True)
    print("Endpoints: /health, /devices, /events?since=0", flush=True)
    print("Close the bridge window to stop.", flush=True)

    win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
    win32gui.UpdateWindow(hwnd)
    win32gui.PumpMessages()


if __name__ == "__main__":
    main()
