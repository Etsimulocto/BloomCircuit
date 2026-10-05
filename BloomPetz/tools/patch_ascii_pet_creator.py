#!/usr/bin/env python3
"""Patch BloomPetz firmware with a buttons-first 4-line pet creator.

Adds one creator screen containing Name / Type / Design / Save and a full
printable ASCII wheel (codes 32..126). Designed to patch the current working
Arduino sketch without replacing proven OLED/touch/USB layers.
"""
from pathlib import Path
import sys

MARKER = "// BLOOMPETZ_ASCII_CREATOR_V1"


def replace_once(s: str, old: str, new: str, label: str) -> str:
    if old not in s:
        raise SystemExit(f"Patch marker not found: {label}")
    return s.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_ascii_pet_creator.py <bloompetz_v0_1.ino>")

    p = Path(sys.argv[1]).expanduser().resolve()
    s = p.read_text()
    if MARKER in s:
        print("ASCII pet creator already applied.")
        return

    s = replace_once(
        s,
        "enum UiMode : uint8_t { HOME, SHOW_SEQUENCE, ENTER_SEQUENCE, RESULT, MENU };",
        "enum UiMode : uint8_t { HOME, SHOW_SEQUENCE, ENTER_SEQUENCE, RESULT, MENU, CREATE_PET };",
        "UiMode enum",
    )

    anchor = "static uint32_t responseStartMs = 0;\n"
    creator = r'''

// BLOOMPETZ_ASCII_CREATOR_V1
// Printable ASCII only: codes 32 (space) through 126 (~). This preserves the
// existing compact OLED font while still exposing every standard printable
// character to the six physical controls.
static uint8_t creatorRow = 0;  // 0 Name, 1 Type, 2 Design, 3 Save
static String creatorName;
static String creatorType;
static String creatorArt;
static char creatorChar = 'A';

static uint8_t creatorMaxLen(uint8_t row) {
  return row == 2 ? 16 : 12;
}

static String &creatorField(uint8_t row) {
  if (row == 0) return creatorName;
  if (row == 1) return creatorType;
  return creatorArt;
}

static String creatorLine(uint8_t row, const char *tag, const String &value) {
  String line = (creatorRow == row ? ">" : " ");
  line += tag;
  line += ":";

  // Keep the current candidate character visible on the selected row.
  if (creatorRow == row) {
    String body = value;
    int room = 16 - line.length() - 2; // '_' + candidate char
    if (room < 0) room = 0;
    if ((int)body.length() > room) body = body.substring(body.length() - room);
    line += body;
    line += '_';
    line += creatorChar;
  } else {
    String body = value;
    int room = 16 - line.length();
    if ((int)body.length() > room) body = body.substring(body.length() - room);
    line += body;
  }
  return line;
}

static void drawCreator() {
  String saveLine = creatorRow == 3 ? ">SAVE A=YES" : " SAVE";
  renderDisplay(
    creatorLine(0, "N", creatorName),
    creatorLine(1, "T", creatorType),
    creatorLine(2, "D", creatorArt),
    saveLine
  );
}

static void beginCreator() {
  creatorRow = 0;
  creatorName = "";
  creatorType = "";
  creatorArt = "";
  creatorChar = 'A';
  uiMode = CREATE_PET;
  drawCreator();
}

static void commitCreator() {
  if (!creatorName.length()) creatorName = "Pet";
  if (!creatorType.length()) creatorType = "Pet";
  if (!creatorArt.length()) creatorArt = "[=^.^=]";
  createPet(activeSlot, creatorName, creatorType, creatorArt);
  uiMode = HOME;
  drawHome();
  printStatus();
}

static void handleCreatorInput(Input in) {
  if (in == UP) {
    creatorRow = (creatorRow + 3) % 4;
    drawCreator();
    return;
  }
  if (in == DOWN) {
    creatorRow = (creatorRow + 1) % 4;
    drawCreator();
    return;
  }

  if (creatorRow == 3) {
    if (in == AKEY) commitCreator();
    else if (in == BKEY) { creatorRow = 2; drawCreator(); }
    return;
  }

  if (in == LEFT) {
    creatorChar = (creatorChar <= 32) ? 126 : (char)(creatorChar - 1);
    drawCreator();
    return;
  }
  if (in == RIGHT) {
    creatorChar = (creatorChar >= 126) ? 32 : (char)(creatorChar + 1);
    drawCreator();
    return;
  }
  if (in == AKEY) {
    String &field = creatorField(creatorRow);
    if (field.length() < creatorMaxLen(creatorRow)) field += creatorChar;
    drawCreator();
    return;
  }
  if (in == BKEY) {
    String &field = creatorField(creatorRow);
    if (field.length()) field.remove(field.length() - 1);
    drawCreator();
    return;
  }
}
'''
    s = replace_once(s, anchor, anchor + creator, "creator state anchor")

    s = replace_once(
        s,
        'renderDisplay("[ no pet ]", "Slot "+String(activeSlot+1), "> CREATE VIA USB", "A INFO  B MENU");',
        'renderDisplay("[ no pet ]", "Slot "+String(activeSlot+1), "> CREATE PET", "A CREATE B MENU");',
        "empty-slot home",
    )

    s = replace_once(
        s,
        "static void handleInput(Input in) {\n  if (in == NONE) return;",
        "static void handleInput(Input in) {\n  if (in == NONE) return;\n  if (uiMode == CREATE_PET) { handleCreatorInput(in); return; }",
        "handleInput entry",
    )

    s = replace_once(
        s,
        "else if (in == AKEY) startAction();",
        "else if (in == AKEY) { if (pets[activeSlot].occupied) startAction(); else beginCreator(); }",
        "HOME A behavior",
    )

    p.write_text(s)
    print(f"ASCII pet creator applied to {p}")
    print("Controls: UP/DOWN rows | LEFT/RIGHT ASCII | A append/save | B delete/back")
    print("Printable character range: ASCII 32..126 (95 characters)")


if __name__ == "__main__":
    main()
