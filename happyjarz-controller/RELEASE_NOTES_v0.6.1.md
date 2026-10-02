# HAPPY JARZ Firmware v0.6.1

## USB touch-stream stability fix

This patch addresses a USB-connected slowdown where the OLED could begin lagging and local capacitive-touch controls could become delayed or appear unresponsive after the desktop controller had been connected for several minutes.

Root cause found in the staged firmware:

- `STREAM TOUCH ON` enabled both `inputStream` and `touchStreamCompat`.
- `serviceInputs()` emitted touch telemetry every 100 ms.
- `serialPoll()` emitted the same touch telemetry again every 100 ms.
- The desktop controller only needs one stream.

v0.6.1 changes:

- keep the proven local `touchRead()` state machine unchanged
- keep the +20% threshold, ~60 ms qualification and baseline drift unchanged
- make `STREAM TOUCH ON` enable only the primary input stream
- disable the duplicate compatibility emitter
- reduce continuous touch telemetry to 5 Hz / 200 ms
- keep local input/OLED/pattern servicing independent from diagnostic telemetry
- add a staged-build verifier requirement for `USB_TOUCH_STREAM_FIX_V1`
- refuse to flash if the duplicate compatibility emitter survives staging

The desktop app remains v1.1.0 because this is a firmware-only behavior fix.
