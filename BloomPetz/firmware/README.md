# BloomPetz Firmware

ESP32-S3 runtime lives here.

Planned module split:

- `bloompetz.ino` — top-level runtime
- `display.*` — four-line OLED renderer
- `touch.*` — six capacitive controls
- `pet_engine.*` — pet simulation/state updates
- `lighting.*` — two APA106 emotional/effect layer
- `save_system.*` — three local pet slots and persistence
- `usb_protocol.*` — host mirror, backup, restore
- `diagnostics.*` — independent subsystem tests

Do not fold editable pet/stat/reaction content into giant source files. Data definitions belong under `../data/` wherever practical.

Preserve the known-good HAPPY JARZ low-level hardware layers when they are brought in; BloomPetz behavior should build above them.
