// HAPPY JARZ USB serial protocol shim v0.1
// This file intentionally does NOT implement APA106 timing.
// It calls the known-good product layer through the hook functions below.

#ifndef HAPPYJARZ_SERIAL_SHIM_V01
#define HAPPYJARZ_SERIAL_SHIM_V01

static const char *HJ_SERIAL_ID = "HJ-001";
static const char *HJ_HW_VERSION = "V1";
static const char *HJ_FW_VERSION = "0.1";

static bool hjTouchStream = false;
static unsigned long hjLastTouchMs = 0;
static String hjRxLine;

// Implement these in the known-good firmware layer.
void hjSetLed(uint8_t led, uint8_t r, uint8_t g, uint8_t b);
void hjSetBrightness(uint8_t percent);
void hjSetPattern(const String &name);
void hjSaveSettings();
void hjRunRgbTest();
void hjRunTouchTest();
void hjReadTouch(uint32_t &c1, uint32_t &c2, uint32_t &up, uint32_t &down);
String hjStatusLine();

static void hjAck(const String &name) {
  Serial.print("HJ|ACK|command=");
  Serial.println(name);
}

static void hjErr(const String &message) {
  Serial.print("HJ|ERR|message=");
  Serial.println(message);
}

static void hjIdentity() {
  Serial.print("HJ|IDENTITY|serial=");
  Serial.print(HJ_SERIAL_ID);
  Serial.print("|hw=");
  Serial.print(HJ_HW_VERSION);
  Serial.print("|fw=");
  Serial.println(HJ_FW_VERSION);
}

static bool hjParseRgb(const String &line, uint8_t led) {
  int r = -1, g = -1, b = -1;
  const char *s = line.c_str();
  if (led == 1) {
    if (sscanf(s, "SET LED1 COLOR %d %d %d", &r, &g, &b) != 3) return false;
  } else {
    if (sscanf(s, "SET LED2 COLOR %d %d %d", &r, &g, &b) != 3) return false;
  }
  if (r < 0 || r > 255 || g < 0 || g > 255 || b < 0 || b > 255) return false;
  hjSetLed(led, (uint8_t)r, (uint8_t)g, (uint8_t)b);
  return true;
}

static void hjHandleCommand(String line) {
  line.trim();
  if (!line.length()) return;

  if (line == "HELLO") {
    hjIdentity();
    return;
  }

  if (line == "PING") {
    Serial.println("HJ|PONG");
    return;
  }

  if (line == "GET STATUS") {
    Serial.println(hjStatusLine());
    return;
  }

  if (line == "GET TOUCH") {
    uint32_t c1, c2, up, down;
    hjReadTouch(c1, c2, up, down);
    Serial.printf("HJ|TOUCH|c1=%lu|c2=%lu|up=%lu|down=%lu\n",
                  (unsigned long)c1, (unsigned long)c2,
                  (unsigned long)up, (unsigned long)down);
    return;
  }

  if (line == "STREAM TOUCH ON") {
    hjTouchStream = true;
    hjAck("STREAM TOUCH ON");
    return;
  }

  if (line == "STREAM TOUCH OFF") {
    hjTouchStream = false;
    hjAck("STREAM TOUCH OFF");
    return;
  }

  if (line.startsWith("SET LED1 COLOR ")) {
    if (hjParseRgb(line, 1)) hjAck("SET LED1 COLOR");
    else hjErr("invalid LED1 RGB values");
    return;
  }

  if (line.startsWith("SET LED2 COLOR ")) {
    if (hjParseRgb(line, 2)) hjAck("SET LED2 COLOR");
    else hjErr("invalid LED2 RGB values");
    return;
  }

  if (line.startsWith("SET BRIGHTNESS ")) {
    int value = line.substring(15).toInt();
    if (value < 0 || value > 100) {
      hjErr("brightness must be 0-100");
      return;
    }
    hjSetBrightness((uint8_t)value);
    hjAck("SET BRIGHTNESS");
    return;
  }

  if (line.startsWith("SET PATTERN ")) {
    String name = line.substring(12);
    name.trim();
    if (!(name == "OFF" || name == "SOLID" || name == "FADE" || name == "RAINBOW" || name == "PULSE")) {
      hjErr("unknown pattern");
      return;
    }
    hjSetPattern(name);
    hjAck("SET PATTERN");
    return;
  }

  if (line == "TEST RGB") {
    hjRunRgbTest();
    Serial.println("HJ|TEST|rgb=PASS");
    return;
  }

  if (line == "TEST TOUCH") {
    hjRunTouchTest();
    Serial.println("HJ|TEST|touch=PASS");
    return;
  }

  if (line == "SAVE") {
    hjSaveSettings();
    hjAck("SAVE");
    return;
  }

  hjErr("unknown command");
}

void hjSerialBegin() {
  hjRxLine.reserve(96);
}

void hjSerialPoll() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n') {
      hjHandleCommand(hjRxLine);
      hjRxLine = "";
    } else if (c != '\r') {
      if (hjRxLine.length() < 160) hjRxLine += c;
      else hjRxLine = "";
    }
  }

  if (hjTouchStream && millis() - hjLastTouchMs >= 100) {
    hjLastTouchMs = millis();
    uint32_t c1, c2, up, down;
    hjReadTouch(c1, c2, up, down);
    Serial.printf("HJ|TOUCH|c1=%lu|c2=%lu|up=%lu|down=%lu\n",
                  (unsigned long)c1, (unsigned long)c2,
                  (unsigned long)up, (unsigned long)down);
  }
}

#endif
