#!/usr/bin/env python3
"""Add a game-style BloomPetz startup splash and 3-slot picker.

Designed for the current locally patched v0.1 firmware. The script does not
replace the firmware wholesale; it adds startup UI around the existing pet,
creator, HOME, OLED, and input systems.

Flow:
  setup finishes -> animated ASCII spiral / BLOOMPETZ splash -> PICK SLOT
  UP/DOWN selects one of three slots
  A on named/occupied slot -> WELCOME BACK -> HOME
  A on empty/unnamed slot -> existing pet creator

The slot picker uses all four OLED rows:
  PICK SLOT
  >1 Lophire
   2 EMPTY
   3 Nimbi
"""
from pathlib import Path
import re
import sys

MARKER = "// BLOOMPETZ_STARTUP_SPLASH_SLOT_PICKER_V1"


def brace_block(text: str, start: int):
    op = text.find('{', start)
    if op < 0:
        raise SystemExit("Opening brace not found")
    depth = 0
    in_string = False
    esc = False
    for i in range(op, len(text)):
        ch = text[i]
        if in_string:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return start, i + 1
    raise SystemExit("Unbalanced brace block")


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_startup_splash_slot_picker.py <bloompetz_v0_1.ino>")

    ino = Path(sys.argv[1]).expanduser().resolve()
    s = ino.read_text()

    if MARKER in s:
        print("Startup splash/slot picker already applied.")
        return

    required = [
        "enum UiMode", "static UiMode uiMode", "static void handleInput(Input in)",
        "static void drawHome()", "static void beginCreator()", "renderDisplay(",
        "pets[", "activeSlot", "PET_SLOT_COUNT"
    ]
    missing = [x for x in required if x not in s]
    if missing:
        raise SystemExit("Required live firmware anchors missing: " + ", ".join(missing))

    # Extend whatever the current UiMode enum contains. Current builds may already
    # include stats modes; preserve them and append startup states exactly once.
    em = re.search(r"enum\s+UiMode\s*:\s*uint8_t\s*\{([^}]*)\};", s, re.S)
    if not em:
        raise SystemExit("UiMode enum not found")
    body = em.group(1).strip()
    if "BOOT_SPLASH" not in body:
        body = body.rstrip()
        if not body.endswith(','):
            body += ','
        body += " BOOT_SPLASH, SLOT_PICKER, WELCOME_BACK"
        s = s[:em.start(1)] + " " + body + " " + s[em.end(1):]

    # Start in BOOT_SPLASH. setup() will explicitly redraw it once hardware/pets
    # are initialized, but this also prevents HOME-only services from taking over.
    s, n = re.subn(
        r"static\s+UiMode\s+uiMode\s*=\s*[^;]+;",
        "static UiMode uiMode = BOOT_SPLASH;",
        s,
        count=1,
    )
    if n != 1:
        raise SystemExit("uiMode initializer not found")

    # Helpers go immediately before handleInput so all existing save/pet/display
    # declarations are already available, while handleInput can call them.
    anchor = "static void handleInput(Input in) {"
    pos = s.find(anchor)
    if pos < 0:
        raise SystemExit("handleInput anchor not found")

    block = r'''// BLOOMPETZ_STARTUP_SPLASH_SLOT_PICKER_V1
static uint8_t startupSlotIndex = 0;
static uint8_t startupSplashFrame = 0;
static uint32_t startupNextMs = 0;
static uint32_t startupWelcomeUntilMs = 0;

static String startupSlotName(uint8_t slot) {
  if (slot >= PET_SLOT_COUNT) return "EMPTY";
  PetSave &p = pets[slot];
  String name = String(p.name);
  name.trim();
  if (!p.occupied || name.length() == 0) return "EMPTY";
  if (name.length() > 12) name = name.substring(0, 12);
  return name;
}

static void drawStartupSlotPicker() {
  String rows[3];
  for (uint8_t i=0; i<3; ++i) {
    rows[i] = String(i == startupSlotIndex ? ">" : " ") + String(i+1) + " " + startupSlotName(i);
  }
  renderDisplay("PICK SLOT", rows[0], rows[1], rows[2]);
}

static void drawStartupSplashFrame(uint8_t frame) {
  // Chunky ASCII spiral intended for the 16-cell OLED text grid.
  switch (frame) {
    case 0:
      renderDisplay("      @", "    @@@", "   @  @", "  BLOOMPETZ");
      break;
    case 1:
      renderDisplay("    @@@", "   @  @@", "   @ @ @", "  BLOOMPETZ");
      break;
    case 2:
      renderDisplay("   @@@@", "  @@  @@", "   @@@ @", "  BLOOMPETZ");
      break;
    default:
      renderDisplay("   @@@@", "  @ @  @", "   @@@@", "  wake up...");
      break;
  }
}

static void beginBootSplash() {
  uiMode = BOOT_SPLASH;
  startupSplashFrame = 0;
  startupNextMs = millis() + 260UL;
  drawStartupSplashFrame(0);
}

static void serviceStartupUi() {
  uint32_t now = millis();
  if (uiMode == BOOT_SPLASH) {
    if ((int32_t)(now - startupNextMs) >= 0) {
      startupSplashFrame++;
      if (startupSplashFrame <= 3) {
        drawStartupSplashFrame(startupSplashFrame);
        startupNextMs = now + (startupSplashFrame == 3 ? 650UL : 260UL);
      } else {
        uiMode = SLOT_PICKER;
        startupSlotIndex = (activeSlot < 3) ? activeSlot : 0;
        drawStartupSlotPicker();
      }
    }
    return;
  }
  if (uiMode == WELCOME_BACK && (int32_t)(now - startupWelcomeUntilMs) >= 0) {
    uiMode = HOME;
    drawHome();
  }
}

static void chooseStartupSlot() {
  activeSlot = startupSlotIndex;
  PetSave &p = pets[activeSlot];
  String name = String(p.name);
  name.trim();
  if (!p.occupied || name.length() == 0) {
    beginCreator();
    return;
  }
  uiMode = WELCOME_BACK;
  startupWelcomeUntilMs = millis() + 700UL;
  renderDisplay(String(p.name), "WELCOME BACK", String(p.art), "...");
}

'''
    s = s[:pos] + block + s[pos:]

    # Handle startup inputs before creator/game/menu modes.
    guard = "  if (in == NONE) return;\n"
    gp = s.find(guard, s.find(anchor))
    if gp < 0:
        raise SystemExit("handleInput NONE guard not found")
    insert_at = gp + len(guard)
    handlers = r'''  if (uiMode == BOOT_SPLASH) {
    // Any navigation input skips the remaining logo animation to slot select.
    if (in == AKEY || in == BKEY || in == UP || in == DOWN || in == LEFT || in == RIGHT) {
      uiMode = SLOT_PICKER;
      startupSlotIndex = (activeSlot < 3) ? activeSlot : 0;
      drawStartupSlotPicker();
    }
    return;
  }
  if (uiMode == SLOT_PICKER) {
    if (in == UP) startupSlotIndex = (startupSlotIndex + 2) % 3;
    else if (in == DOWN) startupSlotIndex = (startupSlotIndex + 1) % 3;
    else if (in == AKEY) { chooseStartupSlot(); return; }
    else return;
    drawStartupSlotPicker();
    return;
  }
  if (uiMode == WELCOME_BACK) {
    if (in == AKEY || in == BKEY) { uiMode = HOME; drawHome(); }
    return;
  }
'''
    s = s[:insert_at] + handlers + s[insert_at:]

    # Replace the final HOME draw in setup if present; otherwise append startup
    # splash at the end of setup. This happens after display and saved pets load.
    setup_start = s.find("void setup() {")
    if setup_start < 0:
        raise SystemExit("setup() not found")
    ss, se = brace_block(s, setup_start)
    setup = s[ss:se]
    draws = list(re.finditer(r"\bdrawHome\s*\(\s*\)\s*;", setup))
    if draws:
        d = draws[-1]
        setup = setup[:d.start()] + "beginBootSplash();" + setup[d.end():]
    else:
        close = setup.rfind('}')
        setup = setup[:close] + "  beginBootSplash();\n" + setup[close:]
    s = s[:ss] + setup + s[se:]

    # Service non-blocking splash/welcome timing every loop. Put it at the top so
    # the startup screen advances even when there is no touch/serial input.
    loop_start = s.find("void loop() {")
    if loop_start < 0:
        raise SystemExit("loop() not found")
    nl = s.find('\n', loop_start)
    if nl < 0:
        raise SystemExit("loop() newline not found")
    s = s[:nl+1] + "  serviceStartupUi();\n" + s[nl+1:]

    ino.write_text(s)
    print(f"Startup splash + slot picker applied to {ino}")
    print("Boot: animated ASCII spiral -> BLOOMPETZ wake up... -> PICK SLOT")
    print("UP/DOWN selects 1-3; A loads named pet or opens creator for EMPTY slot.")
    print("Named pet: WELCOME BACK -> HOME. Any button can skip the splash.")


if __name__ == "__main__":
    main()
