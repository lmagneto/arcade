package com.arcade.tv;

import android.view.InputDevice;
import android.view.MotionEvent;

import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import java.util.ArrayDeque;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.Map;

@CapacitorPlugin(name = "MouseBridge")
public class MouseBridgePlugin extends Plugin {
    private static final Object LOCK = new Object();
    private static final int MAX_DEVICES = 8;
    private static final int MAX_EVENTS = 2000;
    private static final LinkedHashMap<Integer, Integer> DEVICE_SLOTS =
        new LinkedHashMap<>();
    private static final ArrayDeque<BridgeEvent> EVENTS = new ArrayDeque<>();
    private static long nextEventId = 1;

    @PluginMethod
    public void getDevices(PluginCall call) {
        JSArray devices = new JSArray();
        int count;

        synchronized (LOCK) {
            removeDisconnectedDevices();
            for (Map.Entry<Integer, Integer> entry : DEVICE_SLOTS.entrySet()) {
                InputDevice device = InputDevice.getDevice(entry.getKey());
                if (device == null) {
                    continue;
                }

                JSObject item = new JSObject();
                item.put("player_slot", entry.getValue());
                item.put("device_handle", entry.getKey());
                item.put("device_name", device.getName());
                devices.put(item);
            }
            count = DEVICE_SLOTS.size();
        }

        JSObject result = new JSObject();
        result.put("count", count);
        result.put("devices", devices);
        call.resolve(result);
    }

    @PluginMethod
    public void getEvents(PluginCall call) {
        Long since = call.getLong("since", 0L);
        if (since == null || since < 0) {
            call.reject("since must be a non-negative integer");
            return;
        }

        JSArray events = new JSArray();
        long latestId;
        synchronized (LOCK) {
            for (BridgeEvent event : EVENTS) {
                if (event.id > since) {
                    events.put(event.toJSObject());
                }
            }
            latestId = nextEventId - 1;
        }

        JSObject result = new JSObject();
        result.put("events", events);
        result.put("latest_id", latestId);
        call.resolve(result);
    }

    static void recordMotionEvent(MotionEvent event) {
        if ((event.getSource() & InputDevice.SOURCE_MOUSE) != InputDevice.SOURCE_MOUSE) {
            return;
        }

        InputDevice device = InputDevice.getDevice(event.getDeviceId());
        if (device == null) {
            return;
        }

        synchronized (LOCK) {
            int slot = registerDevice(device);
            if (slot == 0) {
                return;
            }

            switch (event.getActionMasked()) {
                case MotionEvent.ACTION_DOWN:
                    addEvent(slot, device, "LEFT_DOWN", 0);
                    break;
                case MotionEvent.ACTION_UP:
                    addEvent(slot, device, "LEFT_UP", 0);
                    break;
                case MotionEvent.ACTION_BUTTON_PRESS:
                case MotionEvent.ACTION_BUTTON_RELEASE:
                    int actionButton = event.getActionButton();
                    String button =
                        actionButton == MotionEvent.BUTTON_PRIMARY
                            ? null
                            : buttonName(actionButton);
                    if (button != null) {
                        boolean down =
                            event.getActionMasked() == MotionEvent.ACTION_BUTTON_PRESS;
                        addEvent(
                            slot,
                            device,
                            button + (down ? "_DOWN" : "_UP"),
                            0
                        );
                    }
                    break;
                case MotionEvent.ACTION_SCROLL:
                    int verticalDelta = wheelDelta(
                        event.getAxisValue(MotionEvent.AXIS_VSCROLL)
                    );
                    int horizontalDelta = wheelDelta(
                        event.getAxisValue(MotionEvent.AXIS_HSCROLL)
                    );
                    if (verticalDelta != 0) {
                        addEvent(slot, device, "WHEEL", verticalDelta);
                    }
                    if (horizontalDelta != 0) {
                        addEvent(
                            slot,
                            device,
                            "HORIZONTAL_WHEEL",
                            horizontalDelta
                        );
                    }
                    break;
                default:
                    break;
            }
        }
    }

    private static int registerDevice(InputDevice device) {
        removeDisconnectedDevices();
        Integer existingSlot = DEVICE_SLOTS.get(device.getId());
        if (existingSlot != null) {
            return existingSlot;
        }
        if (DEVICE_SLOTS.size() >= MAX_DEVICES) {
            return 0;
        }

        boolean[] usedSlots = new boolean[MAX_DEVICES + 1];
        for (int slot : DEVICE_SLOTS.values()) {
            usedSlots[slot] = true;
        }
        for (int slot = 1; slot <= MAX_DEVICES; slot++) {
            if (!usedSlots[slot]) {
                DEVICE_SLOTS.put(device.getId(), slot);
                return slot;
            }
        }
        return 0;
    }

    private static void removeDisconnectedDevices() {
        Iterator<Map.Entry<Integer, Integer>> iterator =
            DEVICE_SLOTS.entrySet().iterator();
        while (iterator.hasNext()) {
            Map.Entry<Integer, Integer> entry = iterator.next();
            InputDevice device = InputDevice.getDevice(entry.getKey());
            if (
                device == null
                    || (device.getSources() & InputDevice.SOURCE_MOUSE)
                        != InputDevice.SOURCE_MOUSE
            ) {
                iterator.remove();
            }
        }

        int slot = 1;
        for (Map.Entry<Integer, Integer> entry : DEVICE_SLOTS.entrySet()) {
            entry.setValue(slot++);
        }
    }

    private static String buttonName(int button) {
        switch (button) {
            case MotionEvent.BUTTON_PRIMARY:
                return "LEFT";
            case MotionEvent.BUTTON_SECONDARY:
                return "RIGHT";
            case MotionEvent.BUTTON_TERTIARY:
                return "MIDDLE";
            case MotionEvent.BUTTON_BACK:
                return "BUTTON4";
            case MotionEvent.BUTTON_FORWARD:
                return "BUTTON5";
            default:
                return null;
        }
    }

    private static int wheelDelta(float value) {
        if (value == 0) {
            return 0;
        }
        int delta = Math.round(value * 120);
        return delta == 0 ? (value > 0 ? 1 : -1) : delta;
    }

    private static void addEvent(
        int slot,
        InputDevice device,
        String button,
        int wheelDelta
    ) {
        BridgeEvent event = new BridgeEvent(
            nextEventId++,
            slot,
            device.getId(),
            device.getName(),
            button,
            wheelDelta
        );
        EVENTS.addLast(event);
        if (EVENTS.size() > MAX_EVENTS) {
            EVENTS.removeFirst();
        }
    }

    private static final class BridgeEvent {
        final long id;
        final int playerSlot;
        final int deviceId;
        final String deviceName;
        final String button;
        final int wheelDelta;

        BridgeEvent(
            long id,
            int playerSlot,
            int deviceId,
            String deviceName,
            String button,
            int wheelDelta
        ) {
            this.id = id;
            this.playerSlot = playerSlot;
            this.deviceId = deviceId;
            this.deviceName = deviceName;
            this.button = button;
            this.wheelDelta = wheelDelta;
        }

        JSObject toJSObject() {
            JSObject result = new JSObject();
            result.put("id", id);
            result.put("player_slot", playerSlot);
            result.put("device_handle", deviceId);
            result.put("device_name", deviceName);
            result.put("button", button);
            result.put("timestamp", System.currentTimeMillis() / 1000.0);
            if (wheelDelta != 0) {
                result.put("wheel_delta", wheelDelta);
            }
            return result;
        }
    }
}
