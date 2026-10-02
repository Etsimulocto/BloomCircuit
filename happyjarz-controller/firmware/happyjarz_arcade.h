#pragma once
#include <Arduino.h>

// HAPPY JARZ board-native arcade layer.
// Logical display space is always 128x64 monochrome.
// This module deliberately does NOT own the OLED driver or touch calibration.
// It consumes edge-triggered button events from the proven six-input layer and
// renders through a tiny display adapter supplied by the known-good OLED code.

enum HjArcadeButton : uint8_t {
  HJ_BTN_UP = 0,
  HJ_BTN_DOWN,
  HJ_BTN_LEFT,
  HJ_BTN_RIGHT,
  HJ_BTN_A,
  HJ_BTN_B,
  HJ_BTN_HOME
};

struct HjArcadeDisplay {
  void (*clear)();
  void (*pixel)(int16_t x, int16_t y, bool on);
  void (*line)(int16_t x0, int16_t y0, int16_t x1, int16_t y1, bool on);
  void (*rect)(int16_t x, int16_t y, int16_t w, int16_t h, bool fill, bool on);
  void (*text)(int16_t x, int16_t y, const char *s, uint8_t size);
  void (*present)();
};

void hjArcadeBegin(const HjArcadeDisplay &display);
void hjArcadeEnter();
void hjArcadeExit();
bool hjArcadeActive();
void hjArcadeButton(HjArcadeButton button);
void hjArcadeService(uint32_t nowMs);
const char *hjArcadeCurrentName();
uint8_t hjArcadeMenuIndex();
