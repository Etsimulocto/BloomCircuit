# HAPPY JARZ Update System

## Goal

A user should be able to plug in a HAPPY JARZ and let the host software determine which compatible release lane applies.

The updater must never guess across incompatible hardware.

## Identity contract

A future device identity should expose enough information to select a release safely.

Example shape:

```text
HJ|IDENTITY|serial=HJ-001|hw=HJ-SIMPLE-1|region=US|fw=0.12.0
```

Capability/status fields may later expose flash/PSRAM information separately.

## Update flow

```text
USB connect
  -> identify HAPPY JARZ
  -> read hardware profile
  -> read provisioned region
  -> read installed firmware version
  -> load release manifest
  -> select compatible lane
  -> compare versions
  -> if current: do nothing
  -> if newer: stop controller/watcher
  -> stage/verify compatible firmware
  -> flash
  -> reconnect
  -> verify identity and expected version
  -> restart host app
```

## Safety rules

1. SIMPLE must never receive a FULL image.
2. FULL must not be assumed from a filename; detect verified board capabilities.
3. Region is provisioned and persisted; do not infer US/EU from location.
4. The update process must verify the staged build before flashing.
5. The host must verify the reported firmware version after flashing.
6. Failed compile or failed verification means **do not upload**.
7. Existing local user settings should survive normal firmware updates unless a documented migration requires otherwise.
8. A recovery/manual flash path must remain available.

## Current status

Architecture scaffold only.

Automatic USB update/install is **not implemented yet**.
