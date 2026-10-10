# HAPPY JARZ Desktop App v1.9.0

## OLED marquee art editor

- Add the 128×64 monochrome editor inside the existing **DISPLAY + INPUT** tab, beside the Custom Marquee tools.
- Add circle drawing, line and rectangle tools, eraser, fill, mirror drawing, undo/redo, and Star, Heart, Diamond, Spark, Smiley, and Flower stamps.
- Save named pictures to the Pi's local `~/.happyjarz/art_library.json` library and export U8g2 C headers.
- Each exported bitmap is 1,024 bytes.
- This release is host-side only. Uploading/persisting images on the jar needs a separate firmware protocol and is not enabled here.

Firmware remains **0.17.13**.
