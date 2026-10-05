#!/usr/bin/env python3
"""Make BloomPetz Mini mirror/play DND correctly.

Patches BOTH the live firmware sketch and desktop/bloompetz_mini.py.

Firmware:
- DND full-width renderer also updates shared screenLines[]
- publishes BP|SCREEN frames only when the 4 DND rows actually change
- launcher label becomes DND instead of DND [SOON]

Desktop:
- accepts up to 21 chars per row (DND full width; BloomPetz still works)
- adds a bottom six-button controller: D-pad + A/B
- button clicks send the same KEY commands as keyboard input
- removes per-screen GET STATUS chatter; status is already requested on connect
- grows the window only by the controller panel height
"""
from pathlib import Path
import re
import sys

FW_MARKER = "// BLOOM_DND_PI_MIRROR_V1"
APP_MARKER = "# BLOOMPETZ_DND_CONTROLS_V1"


def patch_firmware(p: Path) -> None:
    s = p.read_text()
    if FW_MARKER in s:
        print("Firmware DND Pi-mirror patch already applied.")
        return

    if "static void dndRenderFull(const String &r0, const String &r1," not in s:
        raise SystemExit("dndRenderFull() not found in live firmware; refusing to guess")
    if '"DND [SOON]"' in s:
        s = s.replace('"DND [SOON]"', '"DND"', 1)

    start = s.find("static void dndRenderFull(const String &r0, const String &r1,")
    body_open = s.find("{", start)
    if body_open < 0:
        raise SystemExit("dndRenderFull opening brace not found")
    depth = 0
    end = None
    in_string = False
    esc = False
    for i in range(body_open, len(s)):
        ch = s[i]
        if in_string:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        raise SystemExit("Could not bound dndRenderFull()")

    old_fn = s[start:end]
    # Preserve the known ownership guard while replacing the renderer body.
    new_fn = r'''static void dndRenderFull(const String &r0, const String &r1,
                          const String &r2, const String &r3) {
  // BLOOM_DND_PI_MIRROR_V1
  if (uiMode != DND_PLACEHOLDER) return;

  String rows[4] = {
    r0.substring(0, 21), r1.substring(0, 21),
    r2.substring(0, 21), r3.substring(0, 21)
  };

  // DND owns the physical OLED directly: no BloomPetz side gutters.
  oled.clearBuffer();
  oled.setFont(u8g2_font_6x12_tr);
  oled.drawStr(0, 13, rows[0].c_str());
  oled.drawStr(0, 29, rows[1].c_str());
  oled.drawStr(0, 45, rows[2].c_str());
  oled.drawStr(0, 61, rows[3].c_str());
  oled.sendBuffer();

  // Keep the shared mirror buffer current, but only transmit when something
  // actually changed so the 120ms DND render service does not flood USB.
  bool changed = false;
  for (uint8_t i = 0; i < 4; ++i) {
    if (screenLines[i] != rows[i]) {
      screenLines[i] = rows[i];
      changed = true;
    }
  }
  if (changed) {
    Serial.print("BP|SCREEN|1="); Serial.print(screenLines[0]);
    Serial.print("|2="); Serial.print(screenLines[1]);
    Serial.print("|3="); Serial.print(screenLines[2]);
    Serial.print("|4="); Serial.println(screenLines[3]);
  }
}'''
    s = s[:start] + new_fn + s[end:]
    p.write_text(s)
    print(f"Firmware DND mirror patched: {p}")


def patch_desktop(p: Path) -> None:
    s = p.read_text()
    if APP_MARKER in s:
        print("Desktop DND controls patch already applied.")
        return

    # Add controller geometry constants.
    anchor = "SIDE_TICK_MS = 120\n"
    if anchor not in s:
        raise SystemExit("Desktop SIDE_TICK_MS anchor missing")
    s = s.replace(anchor, anchor + f"CONTROL_H = 62\nMIRROR_COLS = 21\n{APP_MARKER}\n", 1)

    # Grow window while preserving existing OLED/header sizing.
    old = 'self.geometry(f"{SCREEN_W}x{SCREEN_H + HEADER_H}")'
    new = 'self.geometry(f"{SCREEN_W}x{SCREEN_H + HEADER_H + CONTROL_H}")'
    if old not in s:
        raise SystemExit("Desktop geometry anchor missing")
    s = s.replace(old, new, 1)

    # Use 21-char backing rows. 16-char BloomPetz rows remain valid and simply pad.
    s = s.replace('self.screen_lines = [" " * 16 for _ in range(4)]',
                  'self.screen_lines = [" " * MIRROR_COLS for _ in range(4)]', 1)

    # Add controls immediately after the screen is packed.
    anchor = '        self.screen.pack_propagate(False)\n'
    if anchor not in s:
        raise SystemExit("Desktop screen pack anchor missing")
    controls = r'''

        # Six-button HAPPY JARZ controller: D-pad + A/B.
        self.controls = tk.Frame(self, bg="#151515", height=CONTROL_H)
        self.controls.pack(fill="x")
        self.controls.pack_propagate(False)

        def add_btn(text, key, x, y, w=34, h=24):
            b = tk.Button(
                self.controls, text=text, command=lambda k=key: self._button_key(k),
                font=("DejaVu Sans", 8, "bold"), bd=1, relief="raised",
                takefocus=False, cursor="hand2"
            )
            b.place(x=x, y=y, width=w, height=h)
            return b

        # Compact D-pad on the left.
        self.btn_up = add_btn("UP", "UP", 38, 2)
        self.btn_left = add_btn("LEFT", "LEFT", 4, 28)
        self.btn_down = add_btn("DOWN", "DOWN", 38, 28)
        self.btn_right = add_btn("RIGHT", "RIGHT", 72, 28)

        # A/B on the right, matching the physical six-input grammar.
        self.btn_a = add_btn("A", "A", 124, 8, 28, 28)
        self.btn_b = add_btn("B", "B", 158, 25, 28, 28)
'''
    s = s.replace(anchor, anchor + controls, 1)

    # Add mouse-button command helper before keyboard handler.
    anchor = "    def _key_press(self, key: str):\n"
    if anchor not in s:
        raise SystemExit("Desktop _key_press anchor missing")
    helper = r'''    def _button_key(self, key: str):
        """Send one discrete controller event, same protocol as keyboard/touch."""
        self.send(f"KEY {key}")
        self.after_idle(self.focus_force)
        return "break"

'''
    s = s.replace(anchor, helper + anchor, 1)

    # Mirror full 21-char DND rows instead of truncating every frame to 16.
    old = 'text = fields.get(str(i+1), self.screen_lines[i])[:16].ljust(16)'
    new = 'text = fields.get(str(i+1), self.screen_lines[i])[:MIRROR_COLS].ljust(MIRROR_COLS)'
    if old not in s:
        raise SystemExit("Desktop 16-char screen parser anchor missing")
    s = s.replace(old, new, 1)

    # Avoid one GET STATUS response per DND frame. It is already fetched on connect.
    s = s.replace('\n        self.send("GET STATUS")\n\n    def close_app', '\n\n    def close_app', 1)

    p.write_text(s)
    print(f"Desktop DND mirror + six controls patched: {p}")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_pi_dnd_mirror_controls.py <bloompetz_v0_1.ino>")
    fw = Path(sys.argv[1]).expanduser().resolve()
    if not fw.exists():
        raise SystemExit(f"Firmware not found: {fw}")
    bloompetz = fw.parents[2]
    desktop = bloompetz / "desktop" / "bloompetz_mini.py"
    if not desktop.exists():
        raise SystemExit(f"Desktop app not found: {desktop}")
    patch_firmware(fw)
    patch_desktop(desktop)
    print("DND now mirrors 21-char frames to Pi and BloomPetz Mini has six clickable controls.")


if __name__ == "__main__":
    main()
