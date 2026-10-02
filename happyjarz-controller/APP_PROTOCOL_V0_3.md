# HAPPY JARZ Desktop Controller Protocol v0.3

This document extends the existing USB CDC protocol without replacing any known-good v0.2 commands.

## Existing commands retained

- `HELLO`
- `PING`
- `GET STATUS`
- `GET TOUCH`
- `STREAM TOUCH ON`
- `STREAM TOUCH OFF`
- `SET LED1 COLOR R G B`
- `SET LED2 COLOR R G B`
- `SET BRIGHTNESS 0-100`
- `SET PATTERN OFF|SOLID|FADE|RAINBOW|PULSE|RANDOM`
- `TEST RGB`
- `TEST TOUCH`
- `SAVE`

## Planned configuration commands

The desktop app may send these before firmware support exists. Unsupported firmware should return its normal unknown-command error; the desktop app remains usable for supported features.

### Device/input

- `GET INPUT`
- `SET INPUT MODE JAR|MENU|GAME`
- `TEST INPUT`

Expected six-input telemetry:

`HJ|INPUT|up=...|down=...|left=...|right=...|a=...|b=...`

Physical control model:

- D-pad: UP, DOWN, LEFT, RIGHT
- A: select / action
- B: back / cancel / escape
- hold B: HOME

### Wi-Fi

- `GET WIFI STATUS`
- `SET WIFI SSID <text>`
- `SET WIFI PASSWORD <text>`
- `SET WIFI CLEAR`
- `WIFI CONNECT`

Password values must never be returned in status or logs.

Suggested responses:

- `HJ|WIFI|state=DISCONNECTED|ssid=<name>|ip=...|rssi=...`
- `HJ|WIFI|state=CONNECTED|ssid=<name>|ip=<addr>|rssi=<dbm>`

### Time

- `GET TIME STATUS`
- `SET TIMEZONE <IANA zone>`
- `TIME SYNC`

Suggested status:

`HJ|TIME|synced=1|timezone=America/Chicago|local=2026-09-30T23:45:00`

### Alarm

- `GET ALARM`
- `SET ALARM HH:MM`
- `SET ALARM ON`
- `SET ALARM OFF`

Suggested status:

`HJ|ALARM|enabled=1|time=07:30`

### Auto-off timer

- `GET TIMER`
- `SET TIMER MINUTES <n>`
- `SET TIMER OFF`

Suggested status:

`HJ|TIMER|enabled=1|minutes=60|remaining=3520`

### Display / screensaver

- `GET DISPLAY`
- `SET DISPLAY BRIGHTNESS 0-100`
- `SET SCREENSAVER OFF|CLOCK|PLASMA|STARS|BOUNCE`
- `SET SCREENSAVER DELAY <minutes>`

### Bulk save

`SAVE` remains the persistence boundary. Configuration commands should update active settings, and `SAVE` commits them to nonvolatile storage.

## Design rule

The desktop controller and OLED UI are two front ends over the same firmware settings and functions. Neither interface should maintain a separate competing configuration model.
