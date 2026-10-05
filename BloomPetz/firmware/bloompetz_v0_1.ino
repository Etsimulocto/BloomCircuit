// BloomPetz integrated firmware v0.1
// bloomcore/v1.3
//
// Purpose:
//   First vertical slice of BloomPetz on ESP32-S3 SuperMini.
//
// Proven hardware preserved from Happy Jarz v0.5:
//   GPIO7 -> 220R -> APA106 #1 DIN -> #2 DIN
//   RMT 10 MHz; 0 = 4/14 ticks, 1 = 14/4 ticks; 100 us latch
//   GPIO4 UP, GPIO5 DOWN, GPIO9 LEFT, GPIO10 RIGHT, GPIO1 A, GPIO2 B
//
// OLED boundary:
//   The known-good OLED driver is not yet in the repository. renderDisplay()
//   emits the exact four 16-character lines over USB as BP|SCREEN records.
//   Replace only the body of physicalOledRender() when the proven OLED layer
//   is brought in. Do not rewrite the pet engine while integrating display.
//
// Vertical slice:
//   - three persistent pet slots
//   - one active pet
//   - 200 developmental floats stored on-device
//   - eight once-per-day developmental actions
//   - randomized three-direction Simon sequence
//   - response-speed gain 0.0001..0.0050
//   - 25 weighted/random stat rolls per completed action
//   - 12.5 food/energy cost per completed action
//   - feed only when empty; restores to 100
//   - three treats/day; each rolls one random developmental stat
//   - midnight resets daily action/treat flags, never the stomach
//   - fixed four-line UI and USB screen mirror
//   - Preferences blob persistence with checksum
//   - independent touch/LED/save diagnostics

#include <Arduino.h>
#include <Preferences.h>
#include <time.h>
#include "esp32-hal-rmt.h"

static const char *BP_FW_VERSION = "0.1.0";
static const char *BP_FORMAT = "bloompetz-save/v1";

static constexpr uint8_t PET_SLOT_COUNT = 3;
static constexpr uint16_t STAT_COUNT = 200;
static constexpr uint8_t STATS_PER_CATEGORY = 10;
static constexpr uint8_t ACTION_COUNT = 8;
static constexpr uint8_t SIMON_LENGTH = 3;
static constexpr uint8_t ACTION_STAT_ROLLS = 25;
static constexpr float ACTION_COST = 12.5f;
static constexpr float FOOD_MAX = 100.0f;
static constexpr float GAIN_MIN = 0.0001f;
static constexpr float GAIN_MAX = 0.0050f;
static constexpr uint8_t TREAT_LIMIT = 3;

static const char *ACTION_NAMES[ACTION_COUNT] = {
  "CHECK", "CLEAN", "PET", "PLAY", "REST", "SCRATCH", "SOCIALIZE", "TRAIN"
};

// Four favored developmental categories per action. Category index * 10 maps
// directly onto the alphabetized JSON category files under ../data/stats/.
// 0 Bond/Social, 1 Courage, 2 Intelligence, 3 Curiosity, 4 Creativity,
// 5 Strength, 6 Defense, 7 Speed, 8 Energy, 9 Health, 10 Food,
// 11 Cleanliness, 12 Emotional, 13 Personality, 14 Habits, 15 Fidget,
// 16 Memory, 17 Luck, 18 Growth, 19 Weird/Hidden.
static const uint8_t ACTION_FAVORED[ACTION_COUNT][4] = {
  {2, 3, 9, 16},    // CHECK
  {9, 11, 14, 12},  // CLEAN
  {0, 12, 13, 15},  // PET
  {7, 1, 4, 15},    // PLAY
  {8, 9, 12, 14},   // REST
  {0, 12, 15, 13},  // SCRATCH
  {0, 12, 13, 4},   // SOCIALIZE (provisional name)
  {1, 2, 5, 16}     // TRAIN (provisional name)
};

// Hardware map — preserve until bench testing says otherwise.
static constexpr uint8_t LED_DATA_PIN = 7;
static constexpr uint8_t INPUT_A_PIN = 1;
static constexpr uint8_t INPUT_B_PIN = 2;
static constexpr uint8_t INPUT_UP_PIN = 4;
static constexpr uint8_t INPUT_DOWN_PIN = 5;
static constexpr uint8_t INPUT_LEFT_PIN = 9;
static constexpr uint8_t INPUT_RIGHT_PIN = 10;
static constexpr uint8_t LED_COUNT = 2;

// APA106 known-good RMT layer.
struct Rgb { uint8_t r, g, b; };
static Rgb ledFrame[LED_COUNT] = {{20, 0, 40}, {0, 20, 40}};
static uint8_t ledBrightness = 40;

static bool initApa106Rmt() {
  pinMode(LED_DATA_PIN, OUTPUT);
  digitalWrite(LED_DATA_PIN, LOW);
  if (!rmtInit(LED_DATA_PIN, RMT_TX_MODE, RMT_MEM_NUM_BLOCKS_1, 10000000)) return false;
  rmtSetEOT(LED_DATA_PIN, 0);
  return true;
}

static void writeApa106(const Rgb frame[LED_COUNT], uint8_t brightness) {
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

static void showLeds() { writeApa106(ledFrame, ledBrightness); }
static void setBoth(Rgb a, Rgb b, uint8_t brightness = 40) {
  ledFrame[0] = a; ledFrame[1] = b; ledBrightness = brightness; showLeds();
}

static void flashDirection(uint8_t dir) {
  static const Rgb colors[4] = {{0,70,8}, {0,20,70}, {55,0,70}, {70,28,0}};
  setBoth(colors[dir], colors[dir], 55);
  delay(250);
  setBoth({3,3,6}, {3,3,6}, 20);
  delay(170);
}

// Six capacitive controls.
enum Input : uint8_t { UP=0, DOWN, LEFT, RIGHT, AKEY, BKEY, NONE=255 };
struct TouchState {
  uint8_t pin;
  const char *name;
  uint32_t baseline;
  uint32_t threshold;
  bool touching;
  bool fired;
  unsigned long enteredMs;
};

static TouchState touchPads[6] = {
  {INPUT_UP_PIN, "UP", 0,0,false,false,0},
  {INPUT_DOWN_PIN, "DOWN", 0,0,false,false,0},
  {INPUT_LEFT_PIN, "LEFT", 0,0,false,false,0},
  {INPUT_RIGHT_PIN, "RIGHT", 0,0,false,false,0},
  {INPUT_A_PIN, "A", 0,0,false,false,0},
  {INPUT_B_PIN, "B", 0,0,false,false,0}
};

static void calibrateTouch() {
  setBoth({0,0,50}, {0,0,50}, 35);
  for (auto &pad : touchPads) {
    uint64_t sum = 0;
    for (int i=0; i<40; ++i) { sum += touchRead(pad.pin); delay(5); }
    pad.baseline = (uint32_t)(sum / 40ULL);
    pad.threshold = pad.baseline + pad.baseline / 5U;
    pad.touching = false; pad.fired = false; pad.enteredMs = 0;
  }
  setBoth({0,50,0}, {0,50,0}, 35); delay(180);
  setBoth({3,3,6}, {3,3,6}, 20);
}

static Input pollInput() {
  unsigned long now = millis();
  for (uint8_t i=0; i<6; ++i) {
    TouchState &pad = touchPads[i];
    uint32_t value = touchRead(pad.pin);
    bool above = value >= pad.threshold;
    if (above && !pad.touching) {
      pad.touching = true; pad.enteredMs = now; pad.fired = false;
    } else if (!above) {
      pad.touching = false; pad.fired = false; pad.enteredMs = 0;
      pad.baseline = (pad.baseline * 127U + value) / 128U;
      pad.threshold = pad.baseline + pad.baseline / 5U;
    }
    if (pad.touching && !pad.fired && (now - pad.enteredMs >= 60)) {
      pad.fired = true;
      return (Input)i;
    }
  }
  return NONE;
}

static const char *inputName(Input in) {
  switch(in) {
    case UP: return "UP"; case DOWN: return "DOWN"; case LEFT: return "LEFT";
    case RIGHT: return "RIGHT"; case AKEY: return "A"; case BKEY: return "B";
    default: return "NONE";
  }
}

// Save model.
struct PetSave {
  uint32_t magic;
  uint16_t version;
  uint16_t size;
  uint32_t checksum;
  bool occupied;
  char name[13];
  char type[13];
  char art[17];
  uint32_t petId;
  uint32_t createdDay;
  uint32_t lastSeenDay;
  uint32_t lifetimeActions;
  uint32_t lifetimeTouches;
  uint32_t lifetimeTreats;
  float foodEnergy;
  uint8_t treatsToday;
  uint8_t dailyActionMask;
  uint8_t reserved[2];
  float stats[STAT_COUNT];
};

static constexpr uint32_t PET_MAGIC = 0x42505A31;
static PetSave pets[PET_SLOT_COUNT];
static uint8_t activeSlot = 0;
static Preferences prefs;

static uint32_t fnv1a(const uint8_t *data, size_t len) {
  uint32_t h = 2166136261UL;
  for (size_t i=0; i<len; ++i) { h ^= data[i]; h *= 16777619UL; }
  return h;
}

static uint32_t petChecksum(PetSave p) {
  p.checksum = 0;
  return fnv1a((const uint8_t*)&p, sizeof(PetSave));
}

static void clearPet(PetSave &p) {
  memset(&p, 0, sizeof(PetSave));
  p.magic = PET_MAGIC; p.version = 1; p.size = sizeof(PetSave); p.foodEnergy = FOOD_MAX;
}

static bool validPet(const PetSave &p) {
  return p.magic == PET_MAGIC && p.version == 1 && p.size == sizeof(PetSave) && p.checksum == petChecksum(p);
}

static String slotKey(uint8_t slot) { return "pet" + String(slot); }

static void saveSlot(uint8_t slot) {
  if (slot >= PET_SLOT_COUNT) return;
  pets[slot].checksum = petChecksum(pets[slot]);
  prefs.begin("bloompetz", false);
  prefs.putBytes(slotKey(slot).c_str(), &pets[slot], sizeof(PetSave));
  prefs.putUChar("active", activeSlot);
  prefs.end();
  Serial.printf("BP|SAVE|slot=%u|ok=1|bytes=%u\n", slot+1, (unsigned)sizeof(PetSave));
}

static void loadAllPets() {
  prefs.begin("bloompetz", true);
  activeSlot = prefs.getUChar("active", 0);
  if (activeSlot >= PET_SLOT_COUNT) activeSlot = 0;
  for (uint8_t i=0; i<PET_SLOT_COUNT; ++i) {
    clearPet(pets[i]);
    size_t got = prefs.getBytes(slotKey(i).c_str(), &pets[i], sizeof(PetSave));
    if (got != sizeof(PetSave) || !validPet(pets[i])) clearPet(pets[i]);
  }
  prefs.end();
}

static void createPet(uint8_t slot, const String &name, const String &type, const String &art) {
  if (slot >= PET_SLOT_COUNT) return;
  clearPet(pets[slot]);
  PetSave &p = pets[slot];
  p.occupied = true;
  name.substring(0,12).toCharArray(p.name, sizeof(p.name));
  type.substring(0,12).toCharArray(p.type, sizeof(p.type));
  art.substring(0,16).toCharArray(p.art, sizeof(p.art));
  p.petId = esp_random();
  p.foodEnergy = FOOD_MAX;
  saveSlot(slot);
}

// Day clock / daily reset. Host may provide YYYY-MM-DD until RTC/NTP is wired into BloomPetz.
static uint32_t manualDay = 0;

static uint32_t currentDayKey() {
  time_t now = time(nullptr);
  if (now > 1700000000) {
    struct tm t; localtime_r(&now, &t);
    return (uint32_t)(t.tm_year + 1900) * 10000UL + (uint32_t)(t.tm_mon + 1) * 100UL + t.tm_mday;
  }
  return manualDay;
}

static void serviceDailyReset(PetSave &p) {
  if (!p.occupied) return;
  uint32_t today = currentDayKey();
  if (!today) return;
  if (p.lastSeenDay == 0) {
    p.lastSeenDay = today;
    if (!p.createdDay) p.createdDay = today;
    saveSlot(activeSlot);
    return;
  }
  if (p.lastSeenDay != today) {
    p.lastSeenDay = today;
    p.dailyActionMask = 0;
    p.treatsToday = 0;
    saveSlot(activeSlot);
    Serial.printf("BP|DAY_RESET|date=%lu|food=%.1f\n", (unsigned long)today, p.foodEnergy);
  }
}

// Display contract. The USB mirror is already live; physical OLED plugs into one function later.
static String screenLines[4] = {"", "", "", ""};
static String fit16(String s) {
  if (s.length() > 16) return s.substring(0,16);
  while (s.length() < 16) s += ' ';
  return s;
}

static void physicalOledRender(const String &, const String &, const String &, const String &) {
  // Integration boundary: paste the proven OLED calls here later.
}

static void renderDisplay(String l1, String l2, String l3, String l4) {
  screenLines[0]=fit16(l1); screenLines[1]=fit16(l2); screenLines[2]=fit16(l3); screenLines[3]=fit16(l4);
  physicalOledRender(screenLines[0],screenLines[1],screenLines[2],screenLines[3]);
  Serial.printf("BP|SCREEN|1=%s|2=%s|3=%s|4=%s\n", screenLines[0].c_str(),screenLines[1].c_str(),screenLines[2].c_str(),screenLines[3].c_str());
}

static String energyWord(float e) {
  if (e >= 76) return "Full"; if (e >= 51) return "Good"; if (e >= 26) return "Peckish";
  if (e > 0) return "Hungry"; return "Empty";
}

// Pet / stat engine.
static float gainFromResponseMs(uint32_t ms) {
  const float fastMs = 600.0f, slowMs = 6000.0f;
  float x = 1.0f - constrain(((float)ms - fastMs) / (slowMs-fastMs), 0.0f, 1.0f);
  return GAIN_MIN + x * (GAIN_MAX - GAIN_MIN);
}

static uint16_t randomStatInCategory(uint8_t cat) {
  return (uint16_t)cat * STATS_PER_CATEGORY + (uint16_t)random(STATS_PER_CATEGORY);
}

static uint16_t chooseActionStat(uint8_t action) {
  if (random(100) < 80) {
    uint8_t cat = ACTION_FAVORED[action][random(4)];
    return randomStatInCategory(cat);
  }
  return (uint16_t)random(STAT_COUNT);
}

static void applyActionGrowth(PetSave &p, uint8_t action, float baseGain) {
  bool hit[STAT_COUNT] = {false};
  uint8_t applied = 0;
  uint16_t attempts = 0;
  while (applied < ACTION_STAT_ROLLS && attempts < 200) {
    ++attempts;
    uint16_t stat = chooseActionStat(action);
    if (hit[stat]) continue;
    hit[stat] = true;
    float wobble = random(850,1151) / 1000.0f;
    float gain = constrain(baseGain * wobble, GAIN_MIN, GAIN_MAX);
    p.stats[stat] = min(1.0f, p.stats[stat] + gain);
    Serial.printf("BP|GAIN|source=%s|stat=%u|amount=%.6f|value=%.6f\n", ACTION_NAMES[action], stat, gain, p.stats[stat]);
    ++applied;
  }
}

static bool actionDone(const PetSave &p, uint8_t action) { return p.dailyActionMask & (1U << action); }
static void markActionDone(PetSave &p, uint8_t action) { p.dailyActionMask |= (1U << action); }

static void giveTreat(PetSave &p) {
  serviceDailyReset(p);
  if (p.treatsToday >= TREAT_LIMIT) {
    renderDisplay(p.art, String(p.name)+" says nope", "NO MORE TREATS", "B BACK");
    setBoth({35,0,10},{35,0,10},25);
    return;
  }
  uint16_t stat = random(STAT_COUNT);
  float gain = random(1,51) / 10000.0f;
  p.stats[stat] = min(1.0f, p.stats[stat] + gain);
  p.treatsToday++;
  p.lifetimeTreats++;
  saveSlot(activeSlot);
  renderDisplay(p.art, String(p.name)+" yum", "TREAT +STAT", String(p.treatsToday)+"/3  B BACK");
  Serial.printf("BP|TREAT|stat=%u|gain=%.6f|today=%u\n", stat, gain, p.treatsToday);
  setBoth({60,20,0},{50,0,35},40);
}

static void feedPet(PetSave &p) {
  serviceDailyReset(p);
  if (p.foodEnergy > 0.01f) {
    renderDisplay(p.art, String(p.name)+" "+energyWord(p.foodEnergy), "STILL HAS FOOD", "B BACK");
    return;
  }
  p.foodEnergy = FOOD_MAX;
  saveSlot(activeSlot);
  renderDisplay(p.art, String(p.name)+" Full", "YUM! ENERGY 100", "A OK   B BACK");
  setBoth({0,55,10},{30,45,0},45);
}

// Simon action state machine.
enum UiMode : uint8_t { HOME, SHOW_SEQUENCE, ENTER_SEQUENCE, RESULT, MENU };
static UiMode uiMode = HOME;
static uint8_t selectedAction = 0;
static uint8_t simon[SIMON_LENGTH];
static uint8_t simonInputIndex = 0;
static uint32_t responseStartMs = 0;

static void drawHome() {
  PetSave &p = pets[activeSlot];
  if (!p.occupied) {
    renderDisplay("[ no pet ]", "Slot "+String(activeSlot+1), "> CREATE VIA USB", "A INFO  B MENU");
    return;
  }
  serviceDailyReset(p);
  String marker = actionDone(p,selectedAction) ? "*" : ">";
  String line3 = marker + String(ACTION_NAMES[selectedAction]);
  String line4 = actionDone(p,selectedAction) ? "A AGAIN B MENU" : "A DO    B MENU";
  renderDisplay(p.art, String(p.name)+" E"+String((int)p.foodEnergy), line3, line4);
}

static void generateSimon() { for (uint8_t i=0;i<SIMON_LENGTH;++i) simon[i]=random(4); }

static void startAction() {
  PetSave &p = pets[activeSlot];
  if (!p.occupied) return;
  serviceDailyReset(p);
  if (p.foodEnergy < ACTION_COST) {
    renderDisplay(p.art, String(p.name)+" Hungry", "NEEDS FOOD", "B BACK");
    return;
  }
  generateSimon();
  uiMode = SHOW_SEQUENCE;
  renderDisplay(p.art, "WATCH", ACTION_NAMES[selectedAction], "...");
  delay(450);
  for (uint8_t i=0;i<SIMON_LENGTH;++i) {
    renderDisplay(p.art, "WATCH", inputName((Input)simon[i]), String(i+1)+"/3");
    flashDirection(simon[i]);
  }
  simonInputIndex = 0;
  responseStartMs = millis();
  uiMode = ENTER_SEQUENCE;
  renderDisplay(p.art, "YOUR TURN", "_ _ _", "B CANCEL");
}

static void failSimon() {
  PetSave &p = pets[activeSlot];
  uiMode = RESULT;
  renderDisplay(p.art, String(p.name)+" o_o", "WRONG - RETRY", "A RETRY B BACK");
  setBoth({60,0,0},{60,0,0},35);
}

static void finishSimon() {
  PetSave &p = pets[activeSlot];
  uint32_t responseMs = millis() - responseStartMs;
  bool firstRewardToday = !actionDone(p, selectedAction);
  float gain = gainFromResponseMs(responseMs);
  p.lifetimeActions++;
  if (firstRewardToday) {
    applyActionGrowth(p, selectedAction, gain);
    markActionDone(p, selectedAction);
    p.foodEnergy = max(0.0f, p.foodEnergy - ACTION_COST);
  }
  saveSlot(activeSlot);
  uiMode = RESULT;
  String result = firstRewardToday ? (String("+")+String(gain,4)+"  E-12.5") : "FUN ONLY TODAY";
  renderDisplay(p.art, String(p.name)+" ^_^", ACTION_NAMES[selectedAction], result);
  Serial.printf("BP|ACTION|name=%s|response_ms=%lu|gain=%.6f|rewarded=%u|energy=%.1f\n", ACTION_NAMES[selectedAction], (unsigned long)responseMs, gain, firstRewardToday?1:0, p.foodEnergy);
  setBoth({0,50,20},{20,20,60},45);
}

static void handleSimonInput(Input in) {
  if (in == BKEY) { uiMode=HOME; drawHome(); return; }
  if (in > RIGHT) return;
  PetSave &p = pets[activeSlot];
  p.lifetimeTouches++;
  if ((uint8_t)in != simon[simonInputIndex]) { failSimon(); return; }
  ++simonInputIndex;
  if (simonInputIndex >= SIMON_LENGTH) { finishSimon(); return; }
  String marks;
  for (uint8_t i=0;i<SIMON_LENGTH;++i) marks += (i<simonInputIndex ? "X " : "_ ");
  renderDisplay(p.art, "YOUR TURN", marks, "B CANCEL");
}

// USB protocol / service console.
static String serialBuffer;

static void printStatus() {
  PetSave &p = pets[activeSlot];
  Serial.printf("BP|STATUS|fw=%s|slot=%u|occupied=%u|name=%s|type=%s|energy=%.1f|actions=0x%02X|treats=%u|day=%lu\n", BP_FW_VERSION,activeSlot+1,p.occupied?1:0,p.name,p.type,p.foodEnergy,p.dailyActionMask,p.treatsToday,(unsigned long)currentDayKey());
}

static void printSlots() {
  for (uint8_t i=0;i<PET_SLOT_COUNT;++i) {
    Serial.printf("BP|SLOT|slot=%u|occupied=%u|name=%s|type=%s|id=%lu\n", i+1,pets[i].occupied?1:0,pets[i].name,pets[i].type,(unsigned long)pets[i].petId);
  }
}

static void printStats() {
  PetSave &p = pets[activeSlot];
  for (uint16_t i=0;i<STAT_COUNT;++i) Serial.printf("BP|STAT|index=%u|value=%.6f\n",i,p.stats[i]);
}

static void diagnosticTouch() {
  for (auto &pad : touchPads) {
    Serial.printf("BP|DIAG|touch=%s|raw=%lu|base=%lu|threshold=%lu\n",pad.name, (unsigned long)touchRead(pad.pin),(unsigned long)pad.baseline,(unsigned long)pad.threshold);
  }
}

static void diagnosticLed() {
  Rgb tests[3]={{80,0,0},{0,80,0},{0,0,80}};
  for (auto c:tests){setBoth(c,c,50);delay(300);} setBoth({3,3,6},{3,3,6},20);
  Serial.println("BP|DIAG|led=PASS_IF_RGB_VISIBLE");
}

static void processCommand(String cmd) {
  cmd.trim();
  if (!cmd.length()) return;
  if (cmd == "HELLO") { Serial.printf("BP|IDENTITY|product=BloomPetz|fw=%s|format=%s\n",BP_FW_VERSION,BP_FORMAT); return; }
  if (cmd == "GET STATUS") { printStatus(); return; }
  if (cmd == "GET SLOTS") { printSlots(); return; }
  if (cmd == "GET STATS") { printStats(); return; }
  if (cmd == "GET SCREEN") { renderDisplay(screenLines[0],screenLines[1],screenLines[2],screenLines[3]); return; }
  if (cmd == "SAVE") { saveSlot(activeSlot); return; }
  if (cmd == "FEED") { if(pets[activeSlot].occupied) feedPet(pets[activeSlot]); return; }
  if (cmd == "TREAT") { if(pets[activeSlot].occupied) giveTreat(pets[activeSlot]); return; }
  if (cmd == "DIAG TOUCH") { diagnosticTouch(); return; }
  if (cmd == "DIAG LED") { diagnosticLed(); return; }
  if (cmd == "RECAL TOUCH") { calibrateTouch(); Serial.println("BP|DIAG|touch_cal=OK"); return; }
  if (cmd.startsWith("SET SLOT ")) {
    int s=cmd.substring(9).toInt(); if(s>=1&&s<=3){activeSlot=s-1;saveSlot(activeSlot);drawHome();} return;
  }
  if (cmd.startsWith("SET DATE ")) {
    String d=cmd.substring(9); d.replace("-",""); manualDay=(uint32_t)d.toInt();
    serviceDailyReset(pets[activeSlot]); Serial.printf("BP|DATE|manual=%lu\n",(unsigned long)manualDay); return;
  }
  if (cmd.startsWith("CREATE ")) {
    String rest=cmd.substring(7); int p1=rest.indexOf('|'); int p2=rest.indexOf('|',p1+1); int p3=rest.indexOf('|',p2+1);
    if(p1>0&&p2>p1&&p3>p2){int s=rest.substring(0,p1).toInt(); if(s>=1&&s<=3){
      createPet(s-1,rest.substring(p1+1,p2),rest.substring(p2+1,p3),rest.substring(p3+1)); activeSlot=s-1; drawHome();}}
    return;
  }
  if (cmd.startsWith("ACTION ")) {
    String name=cmd.substring(7); name.toUpperCase();
    for(uint8_t i=0;i<ACTION_COUNT;++i) if(name==ACTION_NAMES[i]) {selectedAction=i;startAction();return;}
  }
  Serial.printf("BP|ERROR|unknown_command=%s\n",cmd.c_str());
}

static void serviceSerial() {
  while (Serial.available()) {
    char c=(char)Serial.read();
    if(c=='\n' || c=='\r') { if(serialBuffer.length()){processCommand(serialBuffer);serialBuffer="";} }
    else if(serialBuffer.length()<180) serialBuffer += c;
  }
}

// UI input handling.
static void handleInput(Input in) {
  if (in == NONE) return;
  if (uiMode == ENTER_SEQUENCE) { handleSimonInput(in); return; }
  if (uiMode == RESULT) {
    if (in == AKEY) { if(screenLines[2].indexOf("WRONG")>=0) startAction(); else {uiMode=HOME;drawHome();} }
    else if (in == BKEY) {uiMode=HOME;drawHome();}
    return;
  }
  if (uiMode == HOME) {
    if (in == UP) { selectedAction=(selectedAction+ACTION_COUNT-1)%ACTION_COUNT; drawHome(); }
    else if (in == DOWN) { selectedAction=(selectedAction+1)%ACTION_COUNT; drawHome(); }
    else if (in == AKEY) startAction();
    else if (in == BKEY) {
      uiMode=MENU;
      renderDisplay("> FEED", "  TREAT", "  SLOT", "A ENTER B BACK");
    }
    return;
  }
  if (uiMode == MENU) {
    static uint8_t menu=0;
    if (in==UP) menu=(menu+2)%3;
    else if(in==DOWN) menu=(menu+1)%3;
    else if(in==BKEY){uiMode=HOME;drawHome();return;}
    else if(in==AKEY){
      if(menu==0 && pets[activeSlot].occupied) feedPet(pets[activeSlot]);
      else if(menu==1 && pets[activeSlot].occupied) giveTreat(pets[activeSlot]);
      else if(menu==2){activeSlot=(activeSlot+1)%PET_SLOT_COUNT;saveSlot(activeSlot);}
      uiMode=HOME;drawHome();return;
    }
    String m0=(menu==0?"> ":"  ")+String("FEED");
    String m1=(menu==1?"> ":"  ")+String("TREAT");
    String m2=(menu==2?"> ":"  ")+String("SLOT ")+String(activeSlot+1);
    renderDisplay(m0,m1,m2,"A ENTER B BACK");
  }
}

void setup() {
  Serial.begin(115200);
  delay(400);
  randomSeed(esp_random());
  bool ledOk = initApa106Rmt();
  loadAllPets();
  calibrateTouch();
  Serial.printf("BP|BOOT|fw=%s|led=%u|save_bytes=%u|stats=%u\n",BP_FW_VERSION,ledOk?1:0,(unsigned)sizeof(PetSave),STAT_COUNT);
  drawHome();
}

void loop() {
  serviceSerial();
  Input in = pollInput();
  if(in != NONE) handleInput(in);
  static unsigned long lastDayCheck=0;
  if(millis()-lastDayCheck>30000){lastDayCheck=millis(); if(pets[activeSlot].occupied) serviceDailyReset(pets[activeSlot]);}
  delay(4);
}
