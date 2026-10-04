// HAPPY JARZ / CLUB BOX — tunable 8-band line-in EQ visualizer v3.6
//
// Current bench setup: ONE APA106 on GPIO7, mono line-in on GPIO9.
// The analyzer uses 8 Goertzel bands (no extra library dependency).
// The strongest band drives the single LED color; energy drives brightness.
// Band edges/colors and sensitivity can be tuned live from the Pi app.

#include <Arduino.h>
#include <math.h>
#include "esp32-hal-rmt.h"

static constexpr uint8_t LED_DATA_PIN = 7;
static constexpr uint8_t LINE_IN_PIN = 9;
static constexpr uint8_t LED_COUNT = 1;
static constexpr uint8_t BAND_COUNT = 8;
static constexpr uint16_t SAMPLE_COUNT = 256;
static constexpr float SAMPLE_RATE = 8000.0f;
static constexpr uint32_t SAMPLE_PERIOD_US = 125; // 8 kHz
static constexpr unsigned long TELEMETRY_MS = 100;

struct Rgb { uint8_t r, g, b; };

static bool streamEnabled = false;
static String commandBuffer;
static unsigned long lastTelemetry = 0;
static uint8_t maxBrightness = 96;
static float noiseGate = 8.0f;
static float eqGain = 4.0f;

// Tunable band edges. Band i spans edge[i] .. edge[i+1].
static float bandEdge[BAND_COUNT + 1] = {
  40, 90, 180, 350, 700, 1200, 2000, 3000, 3900
};

static Rgb bandColor[BAND_COUNT] = {
  {255, 0, 0},      // sub/bass red
  {255, 70, 0},     // orange
  {255, 180, 0},    // amber
  {80, 255, 0},     // lime
  {0, 255, 90},     // green-cyan
  {0, 180, 255},    // cyan-blue
  {40, 40, 255},    // blue
  {180, 0, 255}     // violet
};

static float samples[SAMPLE_COUNT];
static float bandEnergy[BAND_COUNT] = {};
static uint8_t dominantBand = 0;
static float dominantEnergy = 0.0f;
static uint16_t lastCenter = 0;
static uint16_t lastP2P = 0;
static bool lastClip = false;

static bool initApa106Rmt() {
  pinMode(LED_DATA_PIN, OUTPUT);
  digitalWrite(LED_DATA_PIN, LOW);
  if (!rmtInit(LED_DATA_PIN, RMT_TX_MODE, RMT_MEM_NUM_BLOCKS_1, 10000000)) return false;
  rmtSetEOT(LED_DATA_PIN, 0);
  return true;
}

static void writeRgb(uint8_t r, uint8_t g, uint8_t b) {
  rmt_data_t symbols[24];
  size_t n = 0;
  uint8_t bytes[3] = {r, g, b}; // proven physical order
  for (uint8_t c = 0; c < 3; ++c) {
    for (int bit = 7; bit >= 0; --bit) {
      bool one = bytes[c] & (1U << bit);
      symbols[n].level0 = 1;
      symbols[n].duration0 = one ? 14 : 4;
      symbols[n].level1 = 0;
      symbols[n].duration1 = one ? 4 : 14;
      ++n;
    }
  }
  rmtWrite(LED_DATA_PIN, symbols, n, RMT_WAIT_FOR_EVER);
  digitalWrite(LED_DATA_PIN, LOW);
  delayMicroseconds(100);
}

static uint8_t scale8(uint8_t v, float level) {
  level = constrain(level, 0.0f, 1.0f);
  return (uint8_t)((float)v * level);
}

static void showDominant() {
  if (dominantEnergy <= noiseGate) {
    writeRgb(0, 0, 0);
    return;
  }
  // Energy-to-brightness with a soft compressor so normal line levels remain visible.
  float x = (dominantEnergy - noiseGate) * eqGain;
  float level = x / (x + 80.0f);
  float cap = (float)maxBrightness / 255.0f;
  level *= cap;
  const Rgb &c = bandColor[dominantBand];
  writeRgb(scale8(c.r, level), scale8(c.g, level), scale8(c.b, level));
}

static float goertzelPower(float freq) {
  float k = 0.5f + ((float)SAMPLE_COUNT * freq / SAMPLE_RATE);
  float omega = 2.0f * PI * k / (float)SAMPLE_COUNT;
  float coeff = 2.0f * cosf(omega);
  float q0 = 0, q1 = 0, q2 = 0;
  for (uint16_t i = 0; i < SAMPLE_COUNT; ++i) {
    // Hann window reduces leakage enough for our coarse club-light bands.
    float w = 0.5f - 0.5f * cosf(2.0f * PI * i / (SAMPLE_COUNT - 1));
    q0 = coeff * q1 - q2 + samples[i] * w;
    q2 = q1;
    q1 = q0;
  }
  float power = q1*q1 + q2*q2 - coeff*q1*q2;
  if (power < 0) power = 0;
  return sqrtf(power) / (float)SAMPLE_COUNT;
}

static void sampleAudio() {
  uint32_t next = micros();
  uint32_t sum = 0;
  uint16_t minimum = 4095, maximum = 0;
  uint16_t raw[SAMPLE_COUNT];

  for (uint16_t i = 0; i < SAMPLE_COUNT; ++i) {
    while ((int32_t)(micros() - next) < 0) {}
    uint16_t s = (uint16_t)analogRead(LINE_IN_PIN);
    next += SAMPLE_PERIOD_US;
    raw[i] = s;
    sum += s;
    if (s < minimum) minimum = s;
    if (s > maximum) maximum = s;
  }

  float center = (float)sum / SAMPLE_COUNT;
  lastCenter = (uint16_t)center;
  lastP2P = maximum - minimum;
  lastClip = (minimum <= 25 || maximum >= 4070);
  for (uint16_t i = 0; i < SAMPLE_COUNT; ++i) samples[i] = (float)raw[i] - center;
}

static void analyzeEq() {
  dominantEnergy = 0.0f;
  dominantBand = 0;
  for (uint8_t b = 0; b < BAND_COUNT; ++b) {
    // Sample low/mid/high points inside each tunable band and keep the strongest.
    float lo = bandEdge[b];
    float hi = bandEdge[b+1];
    float f1 = lo + (hi-lo)*0.20f;
    float f2 = lo + (hi-lo)*0.50f;
    float f3 = lo + (hi-lo)*0.80f;
    float e1 = goertzelPower(f1);
    float e2 = goertzelPower(f2);
    float e3 = goertzelPower(f3);
    float e = max(e1, max(e2, e3));
    bandEnergy[b] = e;
    if (e > dominantEnergy) {
      dominantEnergy = e;
      dominantBand = b;
    }
  }
}

static void printEq() {
  if (!Serial) return;
  Serial.printf("HJ|EQ|CENTER=%u|P2P=%u|CLIP=%u|DOM=%u|ENERGY=%.1f",
                (unsigned)lastCenter, (unsigned)lastP2P, lastClip ? 1U : 0U,
                (unsigned)(dominantBand+1), dominantEnergy);
  for (uint8_t b = 0; b < BAND_COUNT; ++b) Serial.printf("|B%u=%.1f", (unsigned)(b+1), bandEnergy[b]);
  Serial.println();
}

static void printConfig() {
  Serial.printf("HJ|EQCFG|GAIN=%.2f|GATE=%.1f|BRIGHT=%u", eqGain, noiseGate, (unsigned)maxBrightness);
  for (uint8_t i = 0; i <= BAND_COUNT; ++i) Serial.printf("|E%u=%.0f", (unsigned)i, bandEdge[i]);
  for (uint8_t b = 0; b < BAND_COUNT; ++b) {
    Serial.printf("|C%u=%u,%u,%u", (unsigned)(b+1), bandColor[b].r, bandColor[b].g, bandColor[b].b);
  }
  Serial.println();
}

static void handleCommand(String cmd) {
  cmd.trim();
  if (!cmd.length()) return;
  if (cmd == "STREAM 1") { streamEnabled = true; Serial.println("HJ|ACK|STREAM=1"); printConfig(); return; }
  if (cmd == "STREAM 0") { streamEnabled = false; return; }
  if (cmd == "GET") { printConfig(); return; }
  if (cmd == "TEST RGB") {
    writeRgb(80,0,0); delay(250); writeRgb(0,80,0); delay(250); writeRgb(0,0,80); delay(250); writeRgb(0,0,0); return;
  }
  if (cmd.startsWith("SET GAIN ")) { float v=cmd.substring(9).toFloat(); if(v>=0.1f&&v<=30.0f) eqGain=v; printConfig(); return; }
  if (cmd.startsWith("SET GATE ")) { float v=cmd.substring(9).toFloat(); if(v>=0&&v<=500) noiseGate=v; printConfig(); return; }
  if (cmd.startsWith("SET BRIGHT ")) { int v=cmd.substring(11).toInt(); if(v>=4&&v<=255) maxBrightness=(uint8_t)v; printConfig(); return; }
  if (cmd.startsWith("SET EDGE ")) {
    int p1=cmd.indexOf(' ',9); if(p1<0) return;
    int idx=cmd.substring(9,p1).toInt(); float hz=cmd.substring(p1+1).toFloat();
    if(idx>=0 && idx<=BAND_COUNT && hz>=20 && hz<=3950) {
      float lower = idx==0 ? 20 : bandEdge[idx-1]+10;
      float upper = idx==BAND_COUNT ? 3950 : bandEdge[idx+1]-10;
      if(hz>=lower && hz<=upper) bandEdge[idx]=hz;
    }
    printConfig(); return;
  }
  if (cmd.startsWith("SET COLOR ")) {
    int p1=cmd.indexOf(' ',10); if(p1<0) return;
    int idx=cmd.substring(10,p1).toInt()-1;
    String rest=cmd.substring(p1+1);
    int c1=rest.indexOf(','); int c2=rest.indexOf(',',c1+1);
    if(idx>=0&&idx<BAND_COUNT&&c1>0&&c2>c1) {
      int r=rest.substring(0,c1).toInt(); int g=rest.substring(c1+1,c2).toInt(); int b=rest.substring(c2+1).toInt();
      bandColor[idx]={(uint8_t)constrain(r,0,255),(uint8_t)constrain(g,0,255),(uint8_t)constrain(b,0,255)};
    }
    printConfig(); return;
  }
}

static void serviceSerial() {
  while (Serial.available() > 0) {
    char ch=(char)Serial.read();
    if(ch=='\n'||ch=='\r') {
      if(commandBuffer.length()) { handleCommand(commandBuffer); commandBuffer=""; }
    } else if(commandBuffer.length()<128) commandBuffer+=ch;
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(LINE_IN_PIN, INPUT);
  analogReadResolution(12);
  if (!initApa106Rmt()) while(true) delay(1000);
  writeRgb(80,0,0); delay(180); writeRgb(0,80,0); delay(180); writeRgb(0,0,80); delay(180); writeRgb(0,0,0);
}

void loop() {
  serviceSerial();
  sampleAudio();
  analyzeEq();
  showDominant();
  unsigned long now=millis();
  if(streamEnabled && now-lastTelemetry>=TELEMETRY_MS) {
    lastTelemetry=now;
    if(Serial.availableForWrite()>=180) printEq();
  }
}
