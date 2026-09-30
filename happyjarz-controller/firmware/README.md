# ESP32 firmware protocol shim

This folder does **not** replace the known-good HAPPY JARZ APA106 RMT driver.

The current bench-proven lower layer uses:

- ESP32-S3 SuperMini
- GPIO7 for APA106 data
- 10 MHz RMT timing
- bit 0 ~= 4 ticks high / 14 ticks low
- bit 1 ~= 14 ticks high / 4 ticks low
- >50 us reset/latch (the known-good build used 100 us)
- two APA106 lamps daisy chained
- GPIO1 / GPIO2 / GPIO4 / GPIO5 touch inputs

`happyjarz_serial_shim.ino` is the USB control layer. Add it alongside the known-good firmware and provide the small hook functions listed below.

## Required firmware hooks

```cpp
void hjSetLed(uint8_t led, uint8_t r, uint8_t g, uint8_t b);
void hjSetBrightness(uint8_t percent);
void hjSetPattern(const String &name);
void hjSaveSettings();
void hjRunRgbTest();
void hjRunTouchTest();
void hjReadTouch(uint32_t &c1, uint32_t &c2, uint32_t &up, uint32_t &down);
String hjStatusLine();
```

Those hooks should call the already-proven product functions. Do not duplicate the LED timing implementation inside the serial parser.

## Main sketch integration

In `setup()`:

```cpp
Serial.begin(115200);
hjSerialBegin();
```

In `loop()`:

```cpp
hjSerialPoll();
```

The shim handles `HELLO`, configuration commands, diagnostics, and optional live touch telemetry.
