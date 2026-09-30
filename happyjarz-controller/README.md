# HAPPY JARZ Controller

**Status:** v0.1 bench/service controller

This subsystem is the PC/Raspberry Pi side of the HAPPY JARZ powered stand.
It deliberately sits *above* the bench-proven ESP32-S3 light/touch layer.

## Design rule

Do not rewrite the known-good APA106 RMT timing to make the desktop controller work.
The controller speaks a small USB-serial protocol; the ESP32 firmware translates those commands into calls to the proven light/touch functions.

## v0.1 scope

- automatically scan USB serial ports
- recognize a HAPPY JARZ device by handshake
- reconnect automatically after unplug/replug
- show device identity (serial / hardware / firmware)
- independently set LED 1 and LED 2 colors
- set brightness
- select a basic pattern
- watch all four capacitive-touch values live
- run RGB / touch diagnostics
- save settings to the Jar
- keep a readable session log

## Hardware map currently expected

- ESP32-S3 SuperMini
- GPIO7 -> 220 ohm -> APA106 #1 DIN
- APA106 #1 DOUT -> APA106 #2 DIN
- GPIO1 = COLOR 1 touch
- GPIO2 = COLOR 2 touch
- GPIO4 = CYCLE UP touch
- GPIO5 = CYCLE DOWN touch

The known-good bench build powers both tested APA106-F8 lamps from the ESP32 3V3 rail and uses one local decoupling capacitor per lamp. This is prototype evidence, not a manufacturer guarantee.

## Desktop requirements

- Python 3.10+
- tkinter (normally included on Windows; on Debian/Raspberry Pi install `python3-tk`)
- pyserial

Install dependency:

```bash
python3 -m pip install -r requirements.txt
```

Run:

```bash
python3 happyjarz_controller.py
```

The app can be left running with no Jar attached. It quietly scans for serial ports and connects when a device answers the HAPPY JARZ handshake.

## Auto-start

### Raspberry Pi / Debian

```bash
bash install_pi_autostart.sh
```

This creates a user autostart desktop entry. The controller launches at login, then waits for a Jar to be plugged in.

### Windows

From PowerShell in this directory:

```powershell
powershell -ExecutionPolicy Bypass -File .\install_windows_autostart.ps1
```

This creates a launcher in the current user's Startup folder. The controller launches at login and waits for the Jar.

## USB protocol

See [`PROTOCOL.md`](PROTOCOL.md).

## Firmware integration

See [`firmware/README.md`](firmware/README.md). The included serial protocol shim is intentionally kept separate from the low-level APA106 driver so a UI bug cannot silently replace the proven pulse timing.

## BloomCore failure boundary

If the desktop UI is wrong but the ESP32's local LED diagnostic still passes, troubleshoot the controller/protocol layer first.

If the ESP32's local LED diagnostic fails, troubleshoot the light layer before changing this application.

Every feature carries its own diagnostic path.
