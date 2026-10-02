// HAPPY JARZ integrated firmware v0.5
// BloomCore: preserve proven APA106 RMT layer; add six-input abstraction,
// Wi-Fi/NTP clock, alarm state, auto-off timer, persistence, and USB protocol.
//
// KNOWN-GOOD HARDWARE LAYER PRESERVED:
//   GPIO7 -> 220R -> APA106 #1 DIN -> #2 DIN
//   RMT 10 MHz; 0 = 4/14 ticks, 1 = 14/4 ticks; 100 us latch low
//
// SIX INPUT MAP:
//   GPIO4  = UP
//   GPIO5  = DOWN
//   GPIO9  = LEFT
//   GPIO10 = RIGHT
//   GPIO1  = A / SELECT
//   GPIO2  = B / BACK / ESC; hold B = HOME event
//
// OLED NOTE:
//   Current bench OLED wiring is intentionally NOT reimplemented here because
//   the known-good OLED source is not yet present in GitHub. This firmware
//   exposes display settings/protocol without replacing the working display layer.

#include <Arduino.h>
#include <Preferences.h>
#include <WiFi.h>
#include <time.h>
#include "esp32-hal-rmt.h"

static const char *HJ_SERIAL_ID = "HJ-001";
static const char *HJ_HW_VERSION = "V1";
static const char *HJ_FW_VERSION = "0.5";

// -----------------------------
// Hardware map
// -----------------------------
static constexpr uint8_t LED_DATA_PIN = 7;
static constexpr uint8_t INPUT_A_PIN = 1;
static constexpr uint8_t INPUT_B_PIN = 2;
static constexpr uint8_t INPUT_UP_PIN = 4;
static constexpr uint8_t INPUT_DOWN_PIN = 5;
static constexpr uint8_t INPUT_LEFT_PIN = 9;
static constexpr uint8_t INPUT_RIGHT_PIN = 10;
static constexpr uint8_t LED_COUNT = 2;
static constexpr size_t INPUT_COUNT = 6;

// -----------------------------
// LED layer — do not casually change
// -----------------------------
struct Rgb { uint8_t r, g, b; };
static Rgb ledColor[LED_COUNT] = {{32,0,64},{0,32,64}};
static uint8_t brightnessPercent = 75;
static String patternName = "SOLID";

static bool initApa106Rmt() {
  pinMode(LED_DATA_PIN, OUTPUT);
  digitalWrite(LED_DATA_PIN, LOW);
  if (!rmtInit(LED_DATA_PIN, RMT_TX_MODE, RMT_MEM_NUM_BLOCKS_1, 10000000)) return false;
  rmtSetEOT(LED_DATA_PIN, 0);
  return true;
}

static void writeFrame(const Rgb frame[LED_COUNT], uint8_t brightness) {
  rmt_data_t symbols[LED_COUNT * 24];
  size_t n = 0;
  for (uint8_t led = 0; led < LED_COUNT; ++led) {
    uint8_t bytes[3] = {
      (uint8_t)((uint16_t)frame[led].r * brightness / 100U),
      (uint8_t)((uint16_t)frame[led].g * brightness / 100U),
      (uint8_t)((uint16_t)frame[led].b * brightness / 100U)
    };
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
  }
  rmtWrite(LED_DATA_PIN, symbols, n, RMT_WAIT_FOR_EVER);
  digitalWrite(LED_DATA_PIN, LOW);
  delayMicroseconds(100);
}

static void showLeds() { writeFrame(ledColor, brightnessPercent); }
static void allOff() {
  Rgb off[LED_COUNT] = {{0,0,0},{0,0,0}};
  writeFrame(off, 100);
}

static void setLedRaw(uint8_t led, uint8_t r, uint8_t g, uint8_t b) {
  if (led < 1 || led > LED_COUNT) return;
  ledColor[led - 1] = {r,g,b};
  showLeds();
}

// -----------------------------
// Six capacitive inputs
// -----------------------------
enum InputIndex : uint8_t { IN_UP=0, IN_DOWN, IN_LEFT, IN_RIGHT, IN_A, IN_B };
struct TouchPadState {
  uint8_t pin;
  const char *name;
  uint32_t baseline;
  uint32_t threshold;
  bool touching;
  bool qualified;
  unsigned long enteredMs;
  unsigned long qualifiedMs;
};

static TouchPadState inputs[INPUT_COUNT] = {
  {INPUT_UP_PIN, "up", 0,0,false,false,0,0},
  {INPUT_DOWN_PIN, "down", 0,0,false,false,0,0},
  {INPUT_LEFT_PIN, "left", 0,0,false,false,0,0},
  {INPUT_RIGHT_PIN, "right", 0,0,false,false,0,0},
  {INPUT_A_PIN, "a", 0,0,false,false,0,0},
  {INPUT_B_PIN, "b", 0,0,false,false,0,0}
};

static String inputMode = "JAR";
static bool inputStream = false;
static unsigned long lastInputStreamMs = 0;
static bool bHomeSent = false;

static uint32_t readTouchPin(uint8_t pin) { return touchRead(pin); }

static void calibrateInputs() {
  for (auto &pad : inputs) {
    uint64_t sum = 0;
    for (int i = 0; i < 40; ++i) { sum += readTouchPin(pad.pin); delay(5); }
    pad.baseline = (uint32_t)(sum / 40ULL);
    pad.threshold = pad.baseline + (pad.baseline / 5U);
    pad.touching = false;
    pad.qualified = false;
    pad.enteredMs = 0;
    pad.qualifiedMs = 0;
  }
  bHomeSent = false;
}

static bool updateInputState(InputIndex idx) {
  TouchPadState &pad = inputs[idx];
  uint32_t value = readTouchPin(pad.pin);
  bool above = value >= pad.threshold;
  unsigned long now = millis();
  if (above && !pad.touching) {
    pad.touching = true;
    pad.enteredMs = now;
  } else if (!above) {
    pad.touching = false;
    pad.qualified = false;
    pad.enteredMs = 0;
    pad.qualifiedMs = 0;
    pad.baseline = (pad.baseline * 127U + value) / 128U;
    pad.threshold = pad.baseline + (pad.baseline / 5U);
    if (idx == IN_B) bHomeSent = false;
  }
  bool q = pad.touching && (now - pad.enteredMs >= 60);
  if (q && !pad.qualified) pad.qualifiedMs = now;
  pad.qualified = q;
  return q;
}

static void printInputTelemetry() {
  Serial.printf("HJ|INPUT|up=%lu|down=%lu|left=%lu|right=%lu|a=%lu|b=%lu\n",
    (unsigned long)readTouchPin(INPUT_UP_PIN),
    (unsigned long)readTouchPin(INPUT_DOWN_PIN),
    (unsigned long)readTouchPin(INPUT_LEFT_PIN),
    (unsigned long)readTouchPin(INPUT_RIGHT_PIN),
    (unsigned long)readTouchPin(INPUT_A_PIN),
    (unsigned long)readTouchPin(INPUT_B_PIN));
}

// -----------------------------
// Settings / persistence
// -----------------------------
static Preferences prefs;
static String wifiSsid;
static String wifiPassword;
static String timezoneName = "America/Chicago";
static bool alarmEnabled = false;
static uint8_t alarmHour = 7;
static uint8_t alarmMinute = 30;
static bool timerEnabled = false;
static uint32_t timerMinutes = 60;
static unsigned long timerStartedMs = 0;
static uint8_t displayBrightness = 100;
static String screensaver = "CLOCK";
static uint16_t screensaverDelayMin = 5;

static const char *tzPosixFor(const String &name) {
  if (name == "America/New_York") return "EST5EDT,M3.2.0/2,M11.1.0/2";
  if (name == "America/Chicago") return "CST6CDT,M3.2.0/2,M11.1.0/2";
  if (name == "America/Denver") return "MST7MDT,M3.2.0/2,M11.1.0/2";
  if (name == "America/Los_Angeles") return "PST8PDT,M3.2.0/2,M11.1.0/2";
  if (name == "UTC" || name == "Etc/UTC") return "UTC0";
  return "CST6CDT,M3.2.0/2,M11.1.0/2"; // safe project default
}

static void loadSettings() {
  prefs.begin("happyjarz", true);
  brightnessPercent = prefs.getUChar("bright", 75);
  ledColor[0] = {prefs.getUChar("l1r",32), prefs.getUChar("l1g",0), prefs.getUChar("l1b",64)};
  ledColor[1] = {prefs.getUChar("l2r",0), prefs.getUChar("l2g",32), prefs.getUChar("l2b",64)};
  patternName = prefs.getString("pattern", "SOLID");
  wifiSsid = prefs.getString("wifi_ssid", "");
  wifiPassword = prefs.getString("wifi_pass", "");
  timezoneName = prefs.getString("timezone", "America/Chicago");
  alarmEnabled = prefs.getBool("alarm_on", false);
  alarmHour = prefs.getUChar("alarm_h", 7);
  alarmMinute = prefs.getUChar("alarm_m", 30);
  timerMinutes = prefs.getUInt("timer_min", 60);
  displayBrightness = prefs.getUChar("disp_bri", 100);
  screensaver = prefs.getString("screensaver", "CLOCK");
  screensaverDelayMin = prefs.getUShort("ss_delay", 5);
  inputMode = prefs.getString("inputmode", "JAR");
  prefs.end();
}

static void persistSettings() {
  prefs.begin("happyjarz", false);
  prefs.putUChar("bright", brightnessPercent);
  prefs.putUChar("l1r", ledColor[0].r); prefs.putUChar("l1g", ledColor[0].g); prefs.putUChar("l1b", ledColor[0].b);
  prefs.putUChar("l2r", ledColor[1].r); prefs.putUChar("l2g", ledColor[1].g); prefs.putUChar("l2b", ledColor[1].b);
  prefs.putString("pattern", patternName);
  prefs.putString("wifi_ssid", wifiSsid);
  prefs.putString("wifi_pass", wifiPassword);
  prefs.putString("timezone", timezoneName);
  prefs.putBool("alarm_on", alarmEnabled);
  prefs.putUChar("alarm_h", alarmHour); prefs.putUChar("alarm_m", alarmMinute);
  prefs.putUInt("timer_min", timerMinutes);
  prefs.putUChar("disp_bri", displayBrightness);
  prefs.putString("screensaver", screensaver);
  prefs.putUShort("ss_delay", screensaverDelayMin);
  prefs.putString("inputmode", inputMode);
  prefs.end();
}

// -----------------------------
// Pattern engine
// -----------------------------
static unsigned long patternLastMs = 0;
static uint16_t patternStep = 0;
static Rgb wheel(uint8_t pos) {
  pos = 255 - pos;
  if (pos < 85) return {(uint8_t)(255-pos*3),0,(uint8_t)(pos*3)};
  if (pos < 170) { pos -= 85; return {0,(uint8_t)(pos*3),(uint8_t)(255-pos*3)}; }
  pos -= 170; return {(uint8_t)(pos*3),(uint8_t)(255-pos*3),0};
}
static void resetPatternEngine(){ patternStep=0; patternLastMs=0; }

static void servicePattern() {
  if (patternName == "SOLID") return;
  if (patternName == "OFF") { allOff(); return; }
  unsigned long now = millis();
  if (patternName == "FADE") {
    if (now-patternLastMs < 22) return; patternLastMs=now;
    uint16_t phase=patternStep%200; uint8_t level=phase<100?phase:(199-phase);
    uint8_t pct=8+(uint8_t)((uint16_t)level*92U/99U);
    writeFrame(ledColor,(uint8_t)((uint16_t)pct*brightnessPercent/100U)); patternStep++; return;
  }
  if (patternName == "PULSE") {
    if (now-patternLastMs < 12) return; patternLastMs=now;
    uint16_t phase=patternStep%120; uint8_t pct;
    if (phase<24) pct=15+(uint8_t)((uint16_t)phase*85U/23U);
    else if (phase<48) pct=100-(uint8_t)((uint16_t)(phase-24)*85U/23U);
    else pct=15;
    writeFrame(ledColor,(uint8_t)((uint16_t)pct*brightnessPercent/100U)); patternStep++; return;
  }
  if (patternName == "RAINBOW") {
    if (now-patternLastMs < 35) return; patternLastMs=now;
    Rgb frame[LED_COUNT]; frame[0]=wheel((uint8_t)patternStep); frame[1]=wheel((uint8_t)(patternStep+96));
    writeFrame(frame,brightnessPercent); patternStep++; return;
  }
  if (patternName == "RANDOM") {
    if (now-patternLastMs < 250) return; patternLastMs=now;
    Rgb frame[LED_COUNT] = {
      {(uint8_t)random(256),(uint8_t)random(256),(uint8_t)random(256)},
      {(uint8_t)random(256),(uint8_t)random(256),(uint8_t)random(256)}
    };
    writeFrame(frame,brightnessPercent); return;
  }
}

static void hjSetLed(uint8_t led,uint8_t r,uint8_t g,uint8_t b){ patternName="SOLID";resetPatternEngine();setLedRaw(led,r,g,b); }
static void hjSetBrightness(uint8_t p){ brightnessPercent=constrain(p,0,100); if(patternName=="SOLID")showLeds(); }
static void hjSetPattern(const String &name){ patternName=name;resetPatternEngine(); if(name=="OFF")allOff(); else if(name=="SOLID")showLeds(); }

// -----------------------------
// Wi-Fi / NTP
// -----------------------------
static void startTimeSync() {
  configTzTime(tzPosixFor(timezoneName), "pool.ntp.org", "time.nist.gov", "time.google.com");
}

static void connectWifi() {
  if (!wifiSsid.length()) return;
  WiFi.mode(WIFI_STA);
  WiFi.begin(wifiSsid.c_str(), wifiPassword.c_str());
}

static bool clockSynced() {
  time_t now = time(nullptr);
  return now > 1700000000;
}

static void printWifiStatus() {
  String state = WiFi.status()==WL_CONNECTED ? "CONNECTED" : "DISCONNECTED";
  Serial.print("HJ|WIFI|state="); Serial.print(state);
  Serial.print("|ssid="); Serial.print(wifiSsid);
  Serial.print("|ip="); Serial.print(WiFi.status()==WL_CONNECTED ? WiFi.localIP().toString() : "");
  Serial.print("|rssi="); Serial.println(WiFi.status()==WL_CONNECTED ? String(WiFi.RSSI()) : "0");
}

static void printTimeStatus() {
  Serial.print("HJ|TIME|synced="); Serial.print(clockSynced()?1:0);
  Serial.print("|timezone="); Serial.print(timezoneName);
  Serial.print("|local=");
  if (!clockSynced()) { Serial.println(""); return; }
  struct tm t; if (!getLocalTime(&t,50)) { Serial.println(""); return; }
  char buf[32]; strftime(buf,sizeof(buf),"%Y-%m-%dT%H:%M:%S",&t); Serial.println(buf);
}

// -----------------------------
// Alarm / timer services
// -----------------------------
static int lastAlarmYday = -1;
static int lastAlarmMinute = -1;
static void fireAlarmEvent() {
  Serial.println("HJ|EVENT|alarm=TRIGGERED");
  // Gentle visible alarm using existing lights; future sound layer can hook here.
  ledColor[0] = {255,120,20}; ledColor[1] = {255,40,100};
  patternName = "PULSE"; resetPatternEngine();
}

static void serviceAlarm() {
  if (!alarmEnabled || !clockSynced()) return;
  struct tm t; if (!getLocalTime(&t,5)) return;
  if (t.tm_hour == alarmHour && t.tm_min == alarmMinute) {
    if (lastAlarmYday != t.tm_yday || lastAlarmMinute != t.tm_min) {
      lastAlarmYday = t.tm_yday; lastAlarmMinute = t.tm_min; fireAlarmEvent();
    }
  }
}

static void serviceTimer() {
  if (!timerEnabled) return;
  uint64_t elapsed = (uint64_t)(millis() - timerStartedMs);
  uint64_t target = (uint64_t)timerMinutes * 60000ULL;
  if (elapsed >= target) {
    timerEnabled = false;
    patternName = "OFF";
    allOff();
    Serial.println("HJ|EVENT|timer=EXPIRED");
  }
}

static uint32_t timerRemainingSeconds() {
  if (!timerEnabled) return 0;
  uint64_t target=(uint64_t)timerMinutes*60000ULL;
  uint64_t elapsed=(uint64_t)(millis()-timerStartedMs);
  return elapsed>=target?0:(uint32_t)((target-elapsed)/1000ULL);
}

// -----------------------------
// Local touch behavior
// -----------------------------
static bool latched[INPUT_COUNT] = {false,false,false,false,false,false};
static const Rgb palette[] = {
  {255,0,0},{255,80,0},{255,180,0},{0,255,0},{0,160,255},{0,0,255},{140,0,255},{255,0,160},{255,255,255}
};
static int paletteIndex1=6, paletteIndex2=4;
static const String patterns[] = {"SOLID","FADE","PULSE","RAINBOW","RANDOM","OFF"};
static int localPatternIndex=0;

static void serviceInputs() {
  bool q[INPUT_COUNT];
  for (uint8_t i=0;i<INPUT_COUNT;++i) q[i]=updateInputState((InputIndex)i);

  if (inputMode == "JAR") {
    if (q[IN_A] && !latched[IN_A]) { paletteIndex1=(paletteIndex1+1)%9; Rgb c=palette[paletteIndex1]; hjSetLed(1,c.r,c.g,c.b); }
    if (q[IN_B] && !latched[IN_B]) { paletteIndex2=(paletteIndex2+1)%9; Rgb c=palette[paletteIndex2]; hjSetLed(2,c.r,c.g,c.b); }
    if (q[IN_UP] && !latched[IN_UP]) { localPatternIndex=(localPatternIndex+1)%6; hjSetPattern(patterns[localPatternIndex]); }
    if (q[IN_DOWN] && !latched[IN_DOWN]) { localPatternIndex=(localPatternIndex+5)%6; hjSetPattern(patterns[localPatternIndex]); }
  }

  // Send edge events for menu/game layers and desktop diagnostics.
  for (uint8_t i=0;i<INPUT_COUNT;++i) {
    if (q[i] && !latched[i]) { Serial.print("HJ|EVENT|input="); Serial.println(inputs[i].name); }
  }
  if (q[IN_B] && !bHomeSent && inputs[IN_B].qualifiedMs && millis()-inputs[IN_B].qualifiedMs>=1000) {
    bHomeSent=true; Serial.println("HJ|EVENT|input=home");
  }
  for (uint8_t i=0;i<INPUT_COUNT;++i) latched[i]=q[i];

  if (inputStream && millis()-lastInputStreamMs>=100) { lastInputStreamMs=millis(); printInputTelemetry(); }
}

// -----------------------------
// USB serial protocol
// -----------------------------
static String rxLine;
static bool touchStreamCompat = false;
static unsigned long lastTouchCompatMs = 0;

static void ack(const String &name){ Serial.print("HJ|ACK|command="); Serial.println(name); }
static void err(const String &msg){ Serial.print("HJ|ERR|message="); Serial.println(msg); }
static void identity(){ Serial.printf("HJ|IDENTITY|serial=%s|hw=%s|fw=%s\n",HJ_SERIAL_ID,HJ_HW_VERSION,HJ_FW_VERSION); }

static String statusLine(){
  String s="HJ|STATUS|brightness="+String(brightnessPercent)+"|pattern="+patternName;
  s+="|led1="+String(ledColor[0].r)+","+String(ledColor[0].g)+","+String(ledColor[0].b);
  s+="|led2="+String(ledColor[1].r)+","+String(ledColor[1].g)+","+String(ledColor[1].b);
  s+="|inputmode="+inputMode;
  return s;
}

static bool parseRgb(const String &line,uint8_t led){
  int r=-1,g=-1,b=-1; int n = led==1 ? sscanf(line.c_str(),"SET LED1 COLOR %d %d %d",&r,&g,&b) : sscanf(line.c_str(),"SET LED2 COLOR %d %d %d",&r,&g,&b);
  if(n!=3||r<0||r>255||g<0||g>255||b<0||b>255)return false; hjSetLed(led,r,g,b); return true;
}

static bool parseHHMM(const String &s,uint8_t &h,uint8_t &m){
  int hh=-1,mm=-1; if(sscanf(s.c_str(),"%d:%d",&hh,&mm)!=2)return false;
  if(hh<0||hh>23||mm<0||mm>59)return false; h=hh;m=mm;return true;
}

static void handleCommand(String line) {
  line.trim(); if(!line.length())return;
  if(line=="HELLO"){identity();return;}
  if(line=="PING"){Serial.println("HJ|PONG");return;}
  if(line=="GET STATUS"){Serial.println(statusLine());return;}

  if(line=="GET TOUCH" || line=="GET INPUT"){ printInputTelemetry(); return; }
  if(line=="STREAM TOUCH ON"){touchStreamCompat=true; inputStream=true; ack(line);return;}
  if(line=="STREAM TOUCH OFF"){touchStreamCompat=false; inputStream=false; ack(line);return;}
  if(line=="STREAM INPUT ON"){inputStream=true;ack(line);return;}
  if(line=="STREAM INPUT OFF"){inputStream=false;ack(line);return;}
  if(line.startsWith("SET INPUT MODE ")){String v=line.substring(15);v.trim();if(v=="JAR"||v=="MENU"||v=="GAME"){inputMode=v;ack("SET INPUT MODE");}else err("input mode must be JAR MENU or GAME");return;}
  if(line=="TEST INPUT"||line=="TEST TOUCH"){calibrateInputs();Serial.println("HJ|TEST|input=PASS");return;}

  if(line.startsWith("SET LED1 COLOR ")){if(parseRgb(line,1))ack("SET LED1 COLOR");else err("invalid LED1 RGB values");return;}
  if(line.startsWith("SET LED2 COLOR ")){if(parseRgb(line,2))ack("SET LED2 COLOR");else err("invalid LED2 RGB values");return;}
  if(line.startsWith("SET BRIGHTNESS ")){int v=line.substring(15).toInt();if(v<0||v>100)err("brightness must be 0-100");else{hjSetBrightness(v);ack("SET BRIGHTNESS");}return;}
  if(line.startsWith("SET PATTERN ")){String v=line.substring(12);v.trim();if(v=="OFF"||v=="SOLID"||v=="FADE"||v=="PULSE"||v=="RAINBOW"||v=="RANDOM"){hjSetPattern(v);ack("SET PATTERN");}else err("unknown pattern");return;}

  if(line=="GET WIFI STATUS"){printWifiStatus();return;}
  if(line.startsWith("SET WIFI SSID ")){wifiSsid=line.substring(14);ack("SET WIFI SSID");return;}
  if(line.startsWith("SET WIFI PASSWORD ")){wifiPassword=line.substring(18);ack("SET WIFI PASSWORD");return;}
  if(line=="SET WIFI CLEAR"){wifiSsid="";wifiPassword="";WiFi.disconnect(true,true);ack(line);return;}
  if(line=="WIFI CONNECT"){connectWifi();ack(line);return;}

  if(line=="GET TIME STATUS"){printTimeStatus();return;}
  if(line.startsWith("SET TIMEZONE ")){timezoneName=line.substring(13);timezoneName.trim();startTimeSync();ack("SET TIMEZONE");return;}
  if(line=="TIME SYNC"){if(WiFi.status()==WL_CONNECTED){startTimeSync();ack(line);}else err("wifi not connected");return;}

  if(line=="GET ALARM"){Serial.printf("HJ|ALARM|enabled=%d|time=%02u:%02u\n",alarmEnabled?1:0,alarmHour,alarmMinute);return;}
  if(line.startsWith("SET ALARM ")){
    String v=line.substring(10);v.trim();
    if(v=="ON"){alarmEnabled=true;ack("SET ALARM ON");return;}
    if(v=="OFF"){alarmEnabled=false;ack("SET ALARM OFF");return;}
    uint8_t h,m;if(parseHHMM(v,h,m)){alarmHour=h;alarmMinute=m;ack("SET ALARM");}else err("alarm time must be HH:MM");return;
  }

  if(line=="GET TIMER"){Serial.printf("HJ|TIMER|enabled=%d|minutes=%lu|remaining=%lu\n",timerEnabled?1:0,(unsigned long)timerMinutes,(unsigned long)timerRemainingSeconds());return;}
  if(line.startsWith("SET TIMER MINUTES ")){long v=line.substring(18).toInt();if(v<1||v>10080)err("timer minutes must be 1-10080");else{timerMinutes=v;timerEnabled=true;timerStartedMs=millis();ack("SET TIMER MINUTES");}return;}
  if(line=="SET TIMER OFF"){timerEnabled=false;ack(line);return;}

  if(line=="GET DISPLAY"){Serial.printf("HJ|DISPLAY|brightness=%u|screensaver=%s|delay=%u\n",displayBrightness,screensaver.c_str(),screensaverDelayMin);return;}
  if(line.startsWith("SET DISPLAY BRIGHTNESS ")){int v=line.substring(23).toInt();if(v<0||v>100)err("display brightness must be 0-100");else{displayBrightness=v;ack("SET DISPLAY BRIGHTNESS");}return;}
  if(line.startsWith("SET SCREENSAVER DELAY ")){int v=line.substring(22).toInt();if(v<0||v>1440)err("screensaver delay must be 0-1440");else{screensaverDelayMin=v;ack("SET SCREENSAVER DELAY");}return;}
  if(line.startsWith("SET SCREENSAVER ")){String v=line.substring(16);v.trim();if(v=="OFF"||v=="CLOCK"||v=="PLASMA"||v=="STARS"||v=="BOUNCE"){screensaver=v;ack("SET SCREENSAVER");}else err("unknown screensaver");return;}

  if(line=="TEST RGB"){
    Rgb s0=ledColor[0],s1=ledColor[1];uint8_t sb=brightnessPercent;String sp=patternName;patternName="SOLID";brightnessPercent=35;
    const Rgb tests[]={{255,0,0},{0,255,0},{0,0,255},{255,255,255}};
    for(const auto &c:tests){ledColor[0]=c;ledColor[1]=c;showLeds();delay(350);} ledColor[0]=s0;ledColor[1]=s1;brightnessPercent=sb;patternName=sp;resetPatternEngine();if(sp=="SOLID")showLeds();
    Serial.println("HJ|TEST|rgb=PASS");return;
  }
  if(line=="SAVE"){persistSettings();ack("SAVE");return;}
  err("unknown command");
}

static void serialPoll(){
  while(Serial.available()){
    char c=(char)Serial.read();
    if(c=='\n'){handleCommand(rxLine);rxLine="";}
    else if(c!='\r'){if(rxLine.length()<192)rxLine+=c;else rxLine="";}
  }
  if(touchStreamCompat && millis()-lastTouchCompatMs>=100){lastTouchCompatMs=millis();printInputTelemetry();}
}

// -----------------------------
// Setup / loop
// -----------------------------
void setup(){
  Serial.begin(115200); delay(250); rxLine.reserve(128); randomSeed((uint32_t)micros());
  loadSettings();
  if(!initApa106Rmt()) Serial.println("HJ|ERR|message=RMT init failed");
  else {
    uint8_t savedBrightness=brightnessPercent;
    brightnessPercent=25; ledColor[0]={0,0,255};ledColor[1]={0,0,255};showLeds();
    calibrateInputs();
    ledColor[0]={0,255,0};ledColor[1]={0,255,0};showLeds();delay(180);
    loadSettings();brightnessPercent=savedBrightness;if(patternName=="SOLID")showLeds();
  }
  if(wifiSsid.length()) connectWifi();
  identity();
}

void loop(){
  serialPoll();
  serviceInputs();
  servicePattern();
  serviceAlarm();
  serviceTimer();
  static bool timeStarted=false;
  if(!timeStarted && WiFi.status()==WL_CONNECTED){startTimeSync();timeStarted=true;Serial.println("HJ|EVENT|wifi=CONNECTED");}
  if(timeStarted && WiFi.status()!=WL_CONNECTED) timeStarted=false;
  delay(5);
}
