
"""ARCADE Windows Raw Input mouse diagnostic.

Run from the project root:
    venv\Scripts\python.exe windows_detector\raw_mouse_test.py
"""

import ctypes
from ctypes import wintypes

import win32api
import win32con
import win32gui

WM_INPUT = 0x00FF
WM_DESTROY = 0x0002
WM_CLOSE = 0x0010

RID_INPUT = 0x10000003
RIDI_DEVICENAME = 0x20000007
RIM_TYPEMOUSE = 0
RIDEV_INPUTSINK = 0x00000100

RI_MOUSE_LEFT_BUTTON_DOWN = 0x0001
RI_MOUSE_LEFT_BUTTON_UP = 0x0002
RI_MOUSE_RIGHT_BUTTON_DOWN = 0x0004
RI_MOUSE_RIGHT_BUTTON_UP = 0x0008
RI_MOUSE_MIDDLE_BUTTON_DOWN = 0x0010
RI_MOUSE_MIDDLE_BUTTON_UP = 0x0020
RI_MOUSE_BUTTON_4_DOWN = 0x0040
RI_MOUSE_BUTTON_4_UP = 0x0080
RI_MOUSE_BUTTON_5_DOWN = 0x0100
RI_MOUSE_BUTTON_5_UP = 0x0200
RI_MOUSE_WHEEL = 0x0400
RI_MOUSE_HWHEEL = 0x0800

BUTTON_EVENTS = (
    (RI_MOUSE_LEFT_BUTTON_DOWN, "LEFT DOWN"),
    (RI_MOUSE_LEFT_BUTTON_UP, "LEFT UP"),
    (RI_MOUSE_RIGHT_BUTTON_DOWN, "RIGHT DOWN"),
    (RI_MOUSE_RIGHT_BUTTON_UP, "RIGHT UP"),
    (RI_MOUSE_MIDDLE_BUTTON_DOWN, "MIDDLE DOWN"),
    (RI_MOUSE_MIDDLE_BUTTON_UP, "MIDDLE UP"),
    (RI_MOUSE_BUTTON_4_DOWN, "BUTTON 4 DOWN"),
    (RI_MOUSE_BUTTON_4_UP, "BUTTON 4 UP"),
    (RI_MOUSE_BUTTON_5_DOWN, "BUTTON 5 DOWN"),
    (RI_MOUSE_BUTTON_5_UP, "BUTTON 5 UP"),
    (RI_MOUSE_WHEEL, "WHEEL"),
    (RI_MOUSE_HWHEEL, "HORIZONTAL WHEEL"),
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


_device_name_cache = {}


def handle_value(handle):
    if handle is None:
        return 0
    try:
        return int(handle)
    except (TypeError, ValueError):
        return int(ctypes.cast(handle, ctypes.c_void_p).value or 0)


def get_device_name(handle):
    key = handle_value(handle)

    if key in _device_name_cache:
        return _device_name_cache[key]

    char_count = wintypes.UINT(0)

    result = user32.GetRawInputDeviceInfoW(
        handle,
        RIDI_DEVICENAME,
        None,
        ctypes.byref(char_count),
    )

    if result == 0xFFFFFFFF or char_count.value == 0:
        name = f"Unknown device (handle={key})"
    else:
        buffer = ctypes.create_unicode_buffer(char_count.value + 1)

        result = user32.GetRawInputDeviceInfoW(
            handle,
            RIDI_DEVICENAME,
            ctypes.cast(buffer, ctypes.c_void_p),
            ctypes.byref(char_count),
        )

        if result == 0xFFFFFFFF:
            name = f"Unknown device (handle={key})"
        else:
            name = buffer.value or f"Unnamed device (handle={key})"

    _device_name_cache[key] = name
    return name


def read_raw_input(hrawinput):
    size = wintypes.UINT(0)
    header_size = ctypes.sizeof(RAWINPUTHEADER)

    result = user32.GetRawInputData(
        hrawinput,
        RID_INPUT,
        None,
        ctypes.byref(size),
        header_size,
    )

    if result == 0xFFFFFFFF or size.value < header_size:
        return None

    buffer = ctypes.create_string_buffer(size.value)

    bytes_read = user32.GetRawInputData(
        hrawinput,
        RID_INPUT,
        ctypes.cast(buffer, ctypes.c_void_p),
        ctypes.byref(size),
        header_size,
    )

    if bytes_read == 0xFFFFFFFF or bytes_read < header_size:
        return None

    if bytes_read < ctypes.sizeof(RAWINPUT):
        return None

    return RAWINPUT.from_buffer_copy(buffer.raw[:bytes_read])


def window_proc(hwnd, msg, wparam, lparam):
    if msg == WM_INPUT:
        try:
            raw = read_raw_input(wintypes.HANDLE(lparam))

            if raw is None or raw.header.dwType != RIM_TYPEMOUSE:
                return 0

            flags = raw.mouse.buttons.button_data.usButtonFlags

            # Ignore ordinary mouse movement.
            if not flags:
                return 0

            device_handle = handle_value(raw.header.hDevice)
            device_name = get_device_name(raw.header.hDevice)

            matched = False

            for flag, label in BUTTON_EVENTS:
                if flags & flag:
                    matched = True
                    extra = ""

                    if flag in (RI_MOUSE_WHEEL, RI_MOUSE_HWHEEL):
                        delta = ctypes.c_short(
                            raw.mouse.buttons.button_data.usButtonData
                        ).value
                        extra = f" | Delta: {delta}"

                    print(
                        f"Handle: {device_handle} | "
                        f"Device: {device_name} | "
                        f"Button: {label}{extra}",
                        flush=True,
                    )

            if not matched:
                print(
                    f"Handle: {device_handle} | Device: {device_name} | "
                    f"Unmapped button flags: 0x{flags:04X}",
                    flush=True,
                )

        except Exception as exc:
            print(f"Raw Input processing error: {exc!r}", flush=True)

        finally:
            # Let Windows perform required WM_INPUT cleanup.
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


def main():
    if ctypes.sizeof(RAWMOUSE) != 24:
        raise RuntimeError(
            f"Unexpected RAWMOUSE size: {ctypes.sizeof(RAWMOUSE)} bytes."
        )

    class_name = "ArcadeRawMouseDiagnostic"
    instance = win32api.GetModuleHandle(None)

    wc = win32gui.WNDCLASS()
    wc.hInstance = instance
    wc.lpszClassName = class_name
    wc.lpfnWndProc = window_proc

    try:
        win32gui.RegisterClass(wc)
    except win32gui.error:
        pass

    hwnd = win32gui.CreateWindow(
        class_name,
        "ARCADE Raw Mouse Diagnostic - close window to stop",
        win32con.WS_OVERLAPPEDWINDOW,
        100,
        100,
        760,
        220,
        0,
        0,
        instance,
        None,
    )

    device = RAWINPUTDEVICE(
        0x01,  # Generic Desktop Controls
        0x02,  # Mouse
        RIDEV_INPUTSINK,
        hwnd,
    )

    if not user32.RegisterRawInputDevices(
        ctypes.byref(device),
        1,
        ctypes.sizeof(RAWINPUTDEVICE),
    ):
        error_code = ctypes.get_last_error()
        win32gui.DestroyWindow(hwnd)
        raise ctypes.WinError(error_code)

    print("ARCADE Raw Input diagnostic is running.")
    print("Click each physical mouse separately.")
    print("Mouse movement is not printed.")
    print("Close the diagnostic window to stop.", flush=True)

    win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
    win32gui.UpdateWindow(hwnd)
    win32gui.PumpMessages()


if __name__ == "__main__":
    main()
