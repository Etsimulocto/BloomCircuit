// ============================================================
// BLOOMCORE MODULE
// ============================================================
// identity:
//   name: BloomGyro
//   module: bloomgyro_v0_1
//   version: 0.1.0
//   format: bloomcore/v1.3
//
// purpose:
//   ESP32-S3 + MPU-6050 three-axis orientation readout with a
//   four-APA106 spatial light ring and capacitive ZERO control.
//
// hardware:
//   controller: ESP32-S3 SuperMini
//   imu: MPU-6050 @ I2C 0x68
//   display: SSD1306 128x64 @ I2C 0x3C
//   leds: 4 x APA106-F8 on one data chain
//
// wiring:
//   I2C SDA       -> GPIO8
//   I2C SCL       -> GPIO6
//   APA106 DATA   -> GPIO7 through 220 ohm
//   ZERO touch    -> GPIO1
//
// LED physical order:
//             LED0
//              ^
//      LED3 <-  +  -> LED1
//              v
//             LED2
//
// color language:
//   GREEN = zero
//   RED   = positive rotation
//   BLUE  = negative rotation
//
// diagnostics:
//   USB serial at 115200 emits BG|... records.
//   Startup checks MPU WHO_AM_I and reports failures.
//
// known-good lower layer:
//   APA106 custom ESP32-S3 RMT timing:
//   10 MHz; 0 = 4/14 ticks, 1 = 14/4 ticks; >=100 us latch.
//
// important limitation:
//   MPU-6050 has no magnetometer. X/Y are gravity-corrected with
//   a complementary filter. Z/yaw is gyro-integrated and will
//   slowly drift. Touch ZERO whenever a fresh reference is needed.
//
// DO NOT:
//   replace the APA106 RMT timing while debugging higher layers.
//   assume Z is magnetic/absolute heading.
// ============================================================

#include <Arduino.h>
#include <Wire.h>
#include <math.h>
#include "esp32-hal-rmt.h"

// Arduino auto-generates prototypes before local type definitions.
// Keep these visible early so generated prototypes remain valid.
struct Rgb;
struct ImuSample;

#if !defined(CONFIG_IDF_TARGET_ESP32S3)
#error BloomGyro requires ESP32-S3
#endif

// ---------------------------- Identity ----------------------------
static const char *BG_VERSION = "0.1.1";
static const char *BG_BUILD = "ZCAL1286";

// ---------------------------- Hardware map ------------------------
static constexpr uint8_t PIN_SDA       = 8;
static constexpr uint8_t PIN_SCL       = 6;
static constexpr uint8_t PIN_LED_DATA  = 7;
static constexpr uint8_t PIN_ZERO      = 1;

static constexpr uint8_t OLED_ADDR = 0x3C;
static constexpr uint8_t MPU_ADDR  = 0x68;
static constexpr uint8_t LED_COUNT = 4;

// ---------------------------- Timing / filter ---------------------
static constexpr float GYRO_SCALE = 131.0f;   // nominal LSB/(deg/s), +/-250 dps
static constexpr float ACC_SCALE  = 16384.0f; // LSB/g, +/-2g
// Repeated 90-degree checks now land at about 70 degrees in both directions.
// That is a consistent scale error, so apply 90/70 = 1.285714 to Z yaw.
// Sign and adaptive stationary bias handling remain separate.
static constexpr float GYRO_Z_CAL = 1.285714f;
static constexpr float COMP_ALPHA = 0.985f;
static constexpr float ZERO_DEADBAND_DEG = 2.0f;
static constexpr float GYRO_STILL_DPS = 0.8f;
static constexpr float STILL_ACCEL_TOL_G = 0.06f;   // |a|-1g tolerance for stillness
static constexpr float STILL_GYRO_XY_DPS = 1.5f;    // X/Y quiet threshold
static constexpr float STILL_GYRO_Z_DPS  = 2.5f;    // Z quiet threshold
static constexpr uint32_t STILL_HOLD_MS  = 450;     // must be still before learning bias
static constexpr float BIAS_LEARN_ALPHA  = 0.0025f; // slow EMA while stationary

static constexpr uint32_t SENSOR_PERIOD_US = 5000;  // 200 Hz
static constexpr uint32_t DISPLAY_PERIOD_MS = 50;   // 20 Hz
static constexpr uint32_t SERIAL_PERIOD_MS = 100;   // 10 Hz

// ---------------------------- Small SSD1306 text driver -----------
// 5x7 font for ASCII 32..127. Each byte is one vertical 7-pixel column.
static const uint8_t FONT5X7[96][5] PROGMEM = {
  {0x00,0x00,0x00,0x00,0x00},{0x00,0x00,0x5F,0x00,0x00},{0x00,0x07,0x00,0x07,0x00},{0x14,0x7F,0x14,0x7F,0x14},
  {0x24,0x2A,0x7F,0x2A,0x12},{0x23,0x13,0x08,0x64,0x62},{0x36,0x49,0x55,0x22,0x50},{0x00,0x05,0x03,0x00,0x00},
  {0x00,0x1C,0x22,0x41,0x00},{0x00,0x41,0x22,0x1C,0x00},{0x14,0x08,0x3E,0x08,0x14},{0x08,0x08,0x3E,0x08,0x08},
  {0x00,0x50,0x30,0x00,0x00},{0x08,0x08,0x08,0x08,0x08},{0x00,0x60,0x60,0x00,0x00},{0x20,0x10,0x08,0x04,0x02},
  {0x3E,0x51,0x49,0x45,0x3E},{0x00,0x42,0x7F,0x40,0x00},{0x42,0x61,0x51,0x49,0x46},{0x21,0x41,0x45,0x4B,0x31},
  {0x18,0x14,0x12,0x7F,0x10},{0x27,0x45,0x45,0x45,0x39},{0x3C,0x4A,0x49,0x49,0x30},{0x01,0x71,0x09,0x05,0x03},
  {0x36,0x49,0x49,0x49,0x36},{0x06,0x49,0x49,0x29,0x1E},{0x00,0x36,0x36,0x00,0x00},{0x00,0x56,0x36,0x00,0x00},
  {0x08,0x14,0x22,0x41,0x00},{0x14,0x14,0x14,0x14,0x14},{0x00,0x41,0x22,0x14,0x08},{0x02,0x01,0x51,0x09,0x06},
  {0x32,0x49,0x79,0x41,0x3E},{0x7E,0x11,0x11,0x11,0x7E},{0x7F,0x49,0x49,0x49,0x36},{0x3E,0x41,0x41,0x41,0x22},
  {0x7F,0x41,0x41,0x22,0x1C},{0x7F,0x49,0x49,0x49,0x41},{0x7F,0x09,0x09,0x09,0x01},{0x3E,0x41,0x49,0x49,0x7A},
  {0x7F,0x08,0x08,0x08,0x7F},{0x00,0x41,0x7F,0x41,0x00},{0x20,0x40,0x41,0x3F,0x01},{0x7F,0x08,0x14,0x22,0x41},
  {0x7F,0x40,0x40,0x40,0x40},{0x7F,0x02,0x0C,0x02,0x7F},{0x7F,0x04,0x08,0x10,0x7F},{0x3E,0x41,0x41,0x41,0x3E},
  {0x7F,0x09,0x09,0x09,0x06},{0x3E,0x41,0x51,0x21,0x5E},{0x7F,0x09,0x19,0x29,0x46},{0x46,0x49,0x49,0x49,0x31},
  {0x01,0x01,0x7F,0x01,0x01},{0x3F,0x40,0x40,0x40,0x3F},{0x1F,0x20,0x40,0x20,0x1F},{0x3F,0x40,0x38,0x40,0x3F},
  {0x63,0x14,0x08,0x14,0x63},{0x07,0x08,0x70,0x08,0x07},{0x61,0x51,0x49,0x45,0x43},{0x00,0x7F,0x41,0x41,0x00},
  {0x02,0x04,0x08,0x10,0x20},{0x00,0x41,0x41,0x7F,0x00},{0x04,0x02,0x01,0x02,0x04},{0x40,0x40,0x40,0x40,0x40},
  {0x00,0x01,0x02,0x04,0x00},{0x20,0x54,0x54,0x54,0x78},{0x7F,0x48,0x44,0x44,0x38},{0x38,0x44,0x44,0x44,0x20},
  {0x38,0x44,0x44,0x48,0x7F},{0x38,0x54,0x54,0x54,0x18},{0x08,0x7E,0x09,0x01,0x02},{0x0C,0x52,0x52,0x52,0x3E},
  {0x7F,0x08,0x04,0x04,0x78},{0x00,0x44,0x7D,0x40,0x00},{0x20,0x40,0x44,0x3D,0x00},{0x7F,0x10,0x28,0x44,0x00},
  {0x00,0x41,0x7F,0x40,0x00},{0x7C,0x04,0x18,0x04,0x78},{0x7C,0x08,0x04,0x04,0x78},{0x38,0x44,0x44,0x44,0x38},
  {0x7C,0x14,0x14,0x14,0x08},{0x08,0x14,0x14,0x18,0x7C},{0x7C,0x08,0x04,0x04,0x08},{0x48,0x54,0x54,0x54,0x20},
  {0x04,0x3F,0x44,0x40,0x20},{0x3C,0x40,0x40,0x20,0x7C},{0x1C,0x20,0x40,0x20,0x1C},{0x3C,0x40,0x30,0x40,0x3C},
  {0x44,0x28,0x10,0x28,0x44},{0x0C,0x50,0x50,0x50,0x3C},{0x44,0x64,0x54,0x4C,0x44},{0x00,0x08,0x36,0x41,0x00},
  {0x00,0x00,0x7F,0x00,0x00},{0x00,0x41,0x36,0x08,0x00},{0x08,0x04,0x08,0x10,0x08},{0x00,0x06,0x09,0x09,0x06}
};

static void i2cWriteReg(uint8_t addr, uint8_t reg, uint8_t value) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  Wire.write(value);
  Wire.endTransmission();
}

static uint8_t i2cReadReg(uint8_t addr, uint8_t reg) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return 0xFF;
  if (Wire.requestFrom((int)addr, 1, true) != 1) return 0xFF;
  return Wire.read();
}

static bool i2cPresent(uint8_t addr) {
  Wire.beginTransmission(addr);
  return Wire.endTransmission() == 0;
}

static void oledCommand(uint8_t cmd) {
  Wire.beginTransmission(OLED_ADDR);
  Wire.write(0x00);
  Wire.write(cmd);
  Wire.endTransmission();
}

static void oledDataChunk(const uint8_t *data, size_t len) {
  while (len) {
    size_t n = len > 16 ? 16 : len;
    Wire.beginTransmission(OLED_ADDR);
    Wire.write(0x40);
    for (size_t i=0; i<n; ++i) Wire.write(data[i]);
    Wire.endTransmission();
    data += n;
    len -= n;
  }
}

static bool oledInit() {
  if (!i2cPresent(OLED_ADDR)) return false;
  const uint8_t initSeq[] = {
    0xAE,       // display off
    0xD5,0x80,  // clock
    0xA8,0x3F,  // mux 1/64
    0xD3,0x00,  // display offset
    0x40,       // start line
    0x8D,0x14,  // charge pump
    0x20,0x00,  // horizontal addressing
    0xA1,       // segment remap
    0xC8,       // COM scan dec
    0xDA,0x12,  // COM pins
    0x81,0x7F,  // contrast
    0xD9,0xF1,  // pre-charge
    0xDB,0x40,  // VCOM detect
    0xA4,       // resume RAM
    0xA6,       // normal display
    0xAF        // display on
  };
  for (uint8_t b : initSeq) oledCommand(b);
  return true;
}

static void oledSetWindow(uint8_t col0, uint8_t col1, uint8_t page0, uint8_t page1) {
  oledCommand(0x21); oledCommand(col0); oledCommand(col1);
  oledCommand(0x22); oledCommand(page0); oledCommand(page1);
}

static void oledClear() {
  static uint8_t zeros[16] = {0};
  oledSetWindow(0,127,0,7);
  for (int i=0; i<64; ++i) oledDataChunk(zeros, sizeof(zeros));
}

static void oledDrawChar(uint8_t x, uint8_t page, char c) {
  if (c < 32 || c > 127) c = '?';
  uint8_t glyph[6];
  uint8_t idx = (uint8_t)c - 32;
  for (uint8_t i=0;i<5;++i) glyph[i] = pgm_read_byte(&FONT5X7[idx][i]);
  glyph[5] = 0;
  oledSetWindow(x, x+5, page, page);
  oledDataChunk(glyph, sizeof(glyph));
}

static void oledText(uint8_t x, uint8_t page, const char *s) {
  while (*s && x <= 121) {
    oledDrawChar(x, page, *s++);
    x += 6;
  }
}

// ---------------------------- APA106 RMT --------------------------
struct Rgb { uint8_t r, g, b; };
static Rgb ledFrame[LED_COUNT] = {};
static uint8_t ledBrightness = 55;

static bool initApa106Rmt() {
  pinMode(PIN_LED_DATA, OUTPUT);
  digitalWrite(PIN_LED_DATA, LOW);
  if (!rmtInit(PIN_LED_DATA, RMT_TX_MODE, RMT_MEM_NUM_BLOCKS_1, 10000000)) return false;
  rmtSetEOT(PIN_LED_DATA, 0);
  return true;
}

static void writeApa106() {
  rmt_data_t symbols[LED_COUNT * 24];
  size_t n = 0;

  for (uint8_t led=0; led<LED_COUNT; ++led) {
    uint8_t bytes[3] = {
      (uint8_t)((uint16_t)ledFrame[led].r * ledBrightness / 100U),
      (uint8_t)((uint16_t)ledFrame[led].g * ledBrightness / 100U),
      (uint8_t)((uint16_t)ledFrame[led].b * ledBrightness / 100U)
    };
    for (uint8_t c=0; c<3; ++c) {
      for (int bit=7; bit>=0; --bit) {
        bool one = bytes[c] & (1U << bit);
        symbols[n].level0 = 1;
        symbols[n].duration0 = one ? 14 : 4;
        symbols[n].level1 = 0;
        symbols[n].duration1 = one ? 4 : 14;
        ++n;
      }
    }
  }

  rmtWrite(PIN_LED_DATA, symbols, n, RMT_WAIT_FOR_EVER);
  digitalWrite(PIN_LED_DATA, LOW);
  delayMicroseconds(100);
}

static void clearLeds() {
  for (auto &p : ledFrame) p = {0,0,0};
}

static uint8_t scale8(float x, uint8_t maxv=90) {
  x = constrain(x, 0.0f, 1.0f);
  return (uint8_t)roundf(x * maxv);
}

// ---------------------------- MPU-6050 ----------------------------
struct ImuSample {
  int16_t ax, ay, az;
  int16_t temp;
  int16_t gx, gy, gz;
};

static float gyroBiasX=0, gyroBiasY=0, gyroBiasZ=0;
static float angleX=0, angleY=0, angleZ=0;
static float zeroX=0, zeroY=0, zeroZ=0;
static float lastGzDps=0;
static bool gyroStill=false;
static uint32_t gyroStillSinceMs=0;
static uint32_t lastSensorUs=0;

// Hardware status is declared here because setZero() may run before the
// setup/loop section and needs to guard optional display/light writes.
static bool oledOk=false;
static bool mpuOk=false;
static bool ledOk=false;

static int16_t be16(const uint8_t *p) {
  return (int16_t)((uint16_t)p[0] << 8 | p[1]);
}

static bool mpuRead(ImuSample &s) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x3B);
  if (Wire.endTransmission(false) != 0) return false;
  uint8_t got = Wire.requestFrom((int)MPU_ADDR, 14, true);
  if (got != 14) return false;

  uint8_t b[14];
  for (uint8_t i=0;i<14;++i) b[i]=Wire.read();
  s.ax=be16(&b[0]); s.ay=be16(&b[2]); s.az=be16(&b[4]);
  s.temp=be16(&b[6]);
  s.gx=be16(&b[8]); s.gy=be16(&b[10]); s.gz=be16(&b[12]);
  return true;
}

static bool mpuInit() {
  if (!i2cPresent(MPU_ADDR)) return false;

  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x75);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom((int)MPU_ADDR, 1, true) != 1) return false;
  uint8_t who = Wire.read();
  // MPU-6050 reports 0x68/0x69. Some drop-in MPU-6500-class boards
  // report 0x70 while using the same basic accel/gyro register map.
  if (who != 0x68 && who != 0x69 && who != 0x70) {
    Serial.printf("BG|ERROR|mpu_whoami=0x%02X\n", who);
    return false;
  }
  Serial.printf("BG|IMU|whoami=0x%02X\n", who);

  i2cWriteReg(MPU_ADDR, 0x6B, 0x01); // wake, PLL with X gyro
  delay(20);
  i2cWriteReg(MPU_ADDR, 0x19, 0x04); // 1kHz/(1+4)=200Hz
  i2cWriteReg(MPU_ADDR, 0x1A, 0x03); // DLPF ~44Hz accel / ~42Hz gyro
  i2cWriteReg(MPU_ADDR, 0x1B, 0x00); // +/-250 dps
  i2cWriteReg(MPU_ADDR, 0x1C, 0x00); // +/-2g
  uint8_t gyroCfg = i2cReadReg(MPU_ADDR, 0x1B);
  Serial.printf("BG|IMU|gyro_config=0x%02X|z_cal=%.6f\n", gyroCfg, GYRO_Z_CAL);
  return true;
}

static void calibrateGyro() {
  Serial.println("BG|CAL|gyro=begin");
  clearLeds();
  for (auto &p : ledFrame) p = {0,30,0};
  ledBrightness=25; writeApa106();

  int64_t sx=0, sy=0, sz=0;
  uint16_t count=0;
  ImuSample s;
  for (uint16_t i=0; i<600; ++i) {
    if (mpuRead(s)) {
      sx += s.gx; sy += s.gy; sz += s.gz; ++count;
    }
    delay(2);
  }
  if (count) {
    gyroBiasX = (float)sx / count;
    gyroBiasY = (float)sy / count;
    gyroBiasZ = (float)sz / count;
  }
  Serial.printf("BG|CAL|gyro=done|samples=%u|bx=%.2f|by=%.2f|bz=%.2f\n",
                count, gyroBiasX, gyroBiasY, gyroBiasZ);
}

static float wrap180(float deg) {
  while (deg > 180.0f) deg -= 360.0f;
  while (deg <= -180.0f) deg += 360.0f;
  return deg;
}

static void updateOrientation(const ImuSample &s, float dt) {
  float ax = (float)s.ax / ACC_SCALE;
  float ay = (float)s.ay / ACC_SCALE;
  float az = (float)s.az / ACC_SCALE;

  // First compute rates from the current bias estimate.
  float gx = ((float)s.gx - gyroBiasX) / GYRO_SCALE;
  float gy = ((float)s.gy - gyroBiasY) / GYRO_SCALE;
  float gzNative = ((float)s.gz - gyroBiasZ) / GYRO_SCALE;

  // Detect true stillness using both gravity magnitude and gyro quietness.
  float amag = sqrtf(ax*ax + ay*ay + az*az);
  bool accelStill = fabsf(amag - 1.0f) <= STILL_ACCEL_TOL_G;
  bool gyroQuiet = fabsf(gx) <= STILL_GYRO_XY_DPS &&
                   fabsf(gy) <= STILL_GYRO_XY_DPS &&
                   fabsf(gzNative) <= STILL_GYRO_Z_DPS;
  bool stillNow = accelStill && gyroQuiet;
  uint32_t nowMs = millis();

  if (stillNow) {
    if (!gyroStill) {
      gyroStill = true;
      gyroStillSinceMs = nowMs;
    } else if ((uint32_t)(nowMs - gyroStillSinceMs) >= STILL_HOLD_MS) {
      // Slowly follow thermal / time-varying zero-rate drift only while
      // motionless. Freeze this immediately when motion begins.
      gyroBiasZ = (1.0f - BIAS_LEARN_ALPHA) * gyroBiasZ +
                  BIAS_LEARN_ALPHA * (float)s.gz;
      gzNative = ((float)s.gz - gyroBiasZ) / GYRO_SCALE;
    }
  } else {
    gyroStill = false;
    gyroStillSinceMs = 0;
  }

  // Clockwise rotation is defined as positive/red for BloomGyro.
  // Native Z sign on this installed 0x70 module is opposite that convention.
  float gz = -(gzNative) * GYRO_Z_CAL;
  lastGzDps = gz;

  float accX = atan2f(ay, az) * 180.0f / PI;
  float accY = atan2f(-ax, sqrtf(ay*ay + az*az)) * 180.0f / PI;

  angleX = COMP_ALPHA * (angleX + gx * dt) + (1.0f-COMP_ALPHA) * accX;
  angleY = COMP_ALPHA * (angleY + gy * dt) + (1.0f-COMP_ALPHA) * accY;
  angleZ += gz * dt;

  // Keep the accumulator numerically tame without changing relative behavior.
  if (angleZ > 10000.0f || angleZ < -10000.0f) {
    float rel = wrap180(angleZ - zeroZ);
    angleZ = rel;
    zeroZ = 0.0f;
  }
}

static float relX() { return wrap180(angleX - zeroX); }
static float relY() { return wrap180(angleY - zeroY); }
// Keep yaw unwrapped so 180/360-degree calibration and multiple turns are
// measurable without a sign jump at the +/-180 boundary.
static float relZ() { return angleZ - zeroZ; }
static float relZWrapped() { return wrap180(relZ()); }

static void setZero() {
  zeroX = angleX;
  zeroY = angleY;
  zeroZ = angleZ;

  clearLeds();
  for (auto &p : ledFrame) p = {0,90,0};
  ledBrightness=50;
  if (ledOk) writeApa106();

  if (oledOk) {
    oledClear();
    oledText(36,2,"ZERO");
    oledText(24,4,"REFERENCE SET");
  }
  Serial.printf("BG|ZERO|x=%.3f|y=%.3f|z=%.3f\n", zeroX, zeroY, zeroZ);
  delay(220);
}

// ---------------------------- Touch ZERO --------------------------
static uint32_t touchBase=0;
static uint32_t touchThreshold=0;
static bool touchActive=false;
static bool touchFired=false;
static uint32_t touchEnteredMs=0;

static void calibrateTouch() {
  uint64_t sum=0;
  for (uint8_t i=0;i<40;++i) { sum += touchRead(PIN_ZERO); delay(5); }
  touchBase = (uint32_t)(sum/40ULL);
  touchThreshold = touchBase + touchBase/5U; // +20%
  Serial.printf("BG|CAL|touch_base=%lu|threshold=%lu\n",
                (unsigned long)touchBase,(unsigned long)touchThreshold);
}

static bool zeroTouchPressed() {
  uint32_t now=millis();
  uint32_t v=touchRead(PIN_ZERO);
  bool above = v >= touchThreshold;

  if (above && !touchActive) {
    touchActive=true;
    touchFired=false;
    touchEnteredMs=now;
  } else if (!above) {
    touchActive=false;
    touchFired=false;
    touchEnteredMs=0;
    touchBase = (touchBase*127U + v)/128U;
    touchThreshold = touchBase + touchBase/5U;
  }

  if (touchActive && !touchFired && now-touchEnteredMs >= 60) {
    touchFired=true;
    return true;
  }
  return false;
}

// ---------------------------- Light ring --------------------------
static void renderLightRing(float zDeg) {
  clearLeds();

  // Physical heading repeats every 360 degrees.  Use wrapped heading only
  // for the "back at zero" test, while keeping the unwrapped sign for color.
  float wrapped = wrap180(zDeg);
  bool atZero = fabsf(wrapped) <= ZERO_DEADBAND_DEG &&
                fabsf(lastGzDps) <= GYRO_STILL_DPS;

  if (atZero) {
    for (auto &p : ledFrame) p = {0,80,0};
    ledBrightness=40;
    writeApa106();
    return;
  }

  // Position always wraps around the four-LED ring.
  // Positive = clockwise/red, negative = counter-clockwise/blue.
  float ringAngle = fmodf(zDeg, 360.0f);
  if (ringAngle < 0) ringAngle += 360.0f;

  float sector = ringAngle / 90.0f;
  int i0 = ((int)floorf(sector)) & 3;
  int i1 = (i0 + 1) & 3;
  float frac = sector - floorf(sector);

  uint8_t a = scale8(1.0f-frac);
  uint8_t b = scale8(frac);

  if (zDeg > 0) {
    ledFrame[i0] = {a,0,0};
    ledFrame[i1] = {b,0,0};
  } else {
    ledFrame[i0] = {0,0,a};
    ledFrame[i1] = {0,0,b};
  }

  ledBrightness=65;
  writeApa106();
}

// ---------------------------- OLED readout ------------------------
static void formatAxis(char *out, size_t n, char axis, float value) {
  char sign = value >= 0 ? '+' : '-';
  float mag = fabsf(value);
  snprintf(out,n,"%c %c%06.1f DEG",axis,sign,mag);
}

static void renderDisplay() {
  char xline[22], yline[22], zline[22];
  formatAxis(xline,sizeof(xline),'X',relX());
  formatAxis(yline,sizeof(yline),'Y',relY());
  formatAxis(zline,sizeof(zline),'Z',relZ());

  oledClear();
  oledText(25,0,"BLOOM GYRO");
  oledText(8,2,xline);
  oledText(8,4,yline);
  oledText(8,6,zline);
}

// ---------------------------- Setup / loop ------------------------
static char serialCmd[40] = {};
static uint8_t serialCmdLen = 0;

static void sendStatus() {
  Serial.printf("BG|STATUS|oled=%u|mpu=%u|led=%u|x=%.2f|y=%.2f|z=%.2f|gz_dps=%.2f|touch=%lu|still=%u|bz=%.2f|build=%s|z_cal=%.6f\n",
                oledOk?1:0,mpuOk?1:0,ledOk?1:0,
                relX(),relY(),relZ(),lastGzDps,(unsigned long)touchRead(PIN_ZERO),
                gyroStill?1:0,gyroBiasZ,BG_BUILD,GYRO_Z_CAL);
}

static void handleSerialCommand(const char *cmd) {
  while (*cmd == ' ' || *cmd == '\t') ++cmd;

  if (!strcasecmp(cmd, "ZERO") || !strcasecmp(cmd, "RESET") ||
      !strcasecmp(cmd, "ZERO RESET")) {
    if (mpuOk) {
      setZero();
      sendStatus();
    } else {
      Serial.println("BG|ERROR|zero_rejected_mpu_unavailable");
    }
    return;
  }

  if (!strcasecmp(cmd, "GET STATUS") || !strcasecmp(cmd, "STATUS")) {
    sendStatus();
    return;
  }

  if (!strcasecmp(cmd, "HELLO")) {
    Serial.printf("BG|IDENTITY|device=BloomGyro|fw=%s|build=%s|z_cal=%.6f|format=bloomcore/v1.3\n", BG_VERSION, BG_BUILD, GYRO_Z_CAL);
    sendStatus();
    return;
  }

  if (*cmd) Serial.printf("BG|ERROR|unknown_command=%s\n", cmd);
}

static void serviceSerialCommands() {
  while (Serial.available() > 0) {
    char ch=(char)Serial.read();
    if (ch == '\r') continue;
    if (ch == '\n') {
      serialCmd[serialCmdLen]='\0';
      handleSerialCommand(serialCmd);
      serialCmdLen=0;
      continue;
    }
    if (serialCmdLen < sizeof(serialCmd)-1) serialCmd[serialCmdLen++]=ch;
  }
}

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.printf("BG|IDENTITY|device=BloomGyro|fw=%s|format=bloomcore/v1.3\n", BG_VERSION);

  Wire.begin(PIN_SDA, PIN_SCL, 400000);

  ledOk = initApa106Rmt();
  oledOk = oledInit();
  mpuOk = mpuInit();

  Serial.printf("BG|BOOT|oled=%u|mpu=%u|led=%u\n",oledOk?1:0,mpuOk?1:0,ledOk?1:0);

  if (!ledOk) {
    Serial.println("BG|ERROR|apa106_rmt_init_failed");
  }

  if (oledOk) {
    oledClear();
    oledText(25,0,"BLOOM GYRO");
    oledText(16,3,mpuOk ? "CALIBRATING" : "MPU NOT FOUND");
  }

  if (!mpuOk) {
    clearLeds();
    for (auto &p : ledFrame) p={70,0,0};
    ledBrightness=45;
    if (ledOk) writeApa106();
    return;
  }

  calibrateGyro();

  // Seed X/Y from gravity so startup does not spend seconds converging.
  ImuSample s;
  if (mpuRead(s)) {
    float ax=(float)s.ax/ACC_SCALE, ay=(float)s.ay/ACC_SCALE, az=(float)s.az/ACC_SCALE;
    angleX = atan2f(ay,az)*180.0f/PI;
    angleY = atan2f(-ax,sqrtf(ay*ay+az*az))*180.0f/PI;
    angleZ = 0.0f;
  }

  calibrateTouch();
  setZero();

  // Visible proof that the latest calibrated firmware is actually running.
  if (oledOk) {
    oledClear();
    oledText(25,0,"BLOOM GYRO");
    oledText(28,3,"FW 0.1.1");
    oledText(19,5,"ZCAL 1.286");
    delay(1800);
  }

  lastSensorUs=micros();
  renderDisplay();
}

void loop() {
  serviceSerialCommands();

  if (!mpuOk) {
    delay(250);
    return;
  }

  uint32_t nowUs=micros();
  if ((uint32_t)(nowUs-lastSensorUs) >= SENSOR_PERIOD_US) {
    float dt=(nowUs-lastSensorUs)/1000000.0f;
    lastSensorUs=nowUs;
    dt=constrain(dt,0.001f,0.05f);

    ImuSample s;
    if (mpuRead(s)) {
      updateOrientation(s,dt);
      renderLightRing(relZ());
    } else {
      Serial.println("BG|ERROR|mpu_read_failed");
    }
  }

  if (zeroTouchPressed()) {
    setZero();
  }

  static uint32_t lastDisplayMs=0;
  static uint32_t lastSerialMs=0;
  uint32_t nowMs=millis();

  if (oledOk && nowMs-lastDisplayMs >= DISPLAY_PERIOD_MS) {
    lastDisplayMs=nowMs;
    renderDisplay();
  }

  if (nowMs-lastSerialMs >= SERIAL_PERIOD_MS) {
    lastSerialMs=nowMs;
    Serial.printf("BG|ANGLES|x=%.2f|y=%.2f|z=%.2f|gz_dps=%.2f|touch=%lu|still=%u|bz=%.2f\n",
                  relX(),relY(),relZ(),lastGzDps,(unsigned long)touchRead(PIN_ZERO),
                  gyroStill?1:0,gyroBiasZ);
  }

  delay(1);
}
