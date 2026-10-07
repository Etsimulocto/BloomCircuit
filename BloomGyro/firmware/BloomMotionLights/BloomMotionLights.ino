// ============================================================
// BloomMotionLights — motion-reactive 4-light test
// ESP32-S3 SuperMini + MPU-6500-class (WHO_AM_I 0x70)
// + SSD1306 OLED + 4x APA106-F8
//
// This is a standalone playground sketch. It does NOT replace the
// production HAPPY JARZ firmware.
//
// Wiring matches BloomGyro:
//   SDA GPIO8
//   SCL GPIO6
//   APA106 DATA GPIO7 through 220R
//   touch/mode GPIO1
// ============================================================

#include <Arduino.h>
#include <Wire.h>
#include <math.h>
#include "esp32-hal-rmt.h"

#if !defined(CONFIG_IDF_TARGET_ESP32S3)
#error BloomMotionLights requires ESP32-S3
#endif

struct Rgb { uint8_t r, g, b; };
struct ImuSample { int16_t ax, ay, az, temp, gx, gy, gz; };

static constexpr uint8_t PIN_SDA=8;
static constexpr uint8_t PIN_SCL=6;
static constexpr uint8_t PIN_LED_DATA=7;
static constexpr uint8_t PIN_TOUCH=1;
static constexpr uint8_t OLED_ADDR=0x3C;
static constexpr uint8_t MPU_ADDR=0x68;
static constexpr uint8_t LED_COUNT=4;

static constexpr float ACC_SCALE=16384.0f;
static constexpr float GYRO_SCALE=131.0f;

static constexpr uint32_t SENSOR_PERIOD_US=5000; // 200 Hz
static constexpr uint32_t LED_PERIOD_MS=20;      // 50 Hz
static constexpr uint32_t OLED_PERIOD_MS=200;    // 5 Hz

static Rgb leds[LED_COUNT] = {};
static float biasX=0, biasY=0, biasZ=0;
static float tiltX=0, tiltY=0;
static float gxDps=0, gyDps=0, gzDps=0;
static float motionEnergy=0;
static float shakePulse=0;
static float hueSpin=0;
static uint32_t lastSensorUs=0;
static uint32_t lastLedMs=0;
static uint32_t lastOledMs=0;
static uint8_t mode=0;

// ---------------- I2C helpers ----------------
static bool i2cPresent(uint8_t addr) {
  Wire.beginTransmission(addr);
  return Wire.endTransmission()==0;
}

static void writeReg(uint8_t reg, uint8_t value) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  Wire.write(value);
  Wire.endTransmission();
}

static int16_t be16(const uint8_t *p) {
  return (int16_t)(((uint16_t)p[0]<<8)|p[1]);
}

static bool readImu(ImuSample &s) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x3B);
  if (Wire.endTransmission(false)!=0) return false;
  if (Wire.requestFrom((int)MPU_ADDR,14,true)!=14) return false;
  uint8_t b[14];
  for (int i=0;i<14;i++) b[i]=Wire.read();
  s.ax=be16(&b[0]); s.ay=be16(&b[2]); s.az=be16(&b[4]);
  s.temp=be16(&b[6]);
  s.gx=be16(&b[8]); s.gy=be16(&b[10]); s.gz=be16(&b[12]);
  return true;
}

static bool initImu() {
  if (!i2cPresent(MPU_ADDR)) return false;

  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x75);
  if (Wire.endTransmission(false)!=0) return false;
  if (Wire.requestFrom((int)MPU_ADDR,1,true)!=1) return false;
  uint8_t who=Wire.read();
  Serial.printf("BML|IMU|whoami=0x%02X\n",who);
  if (who!=0x68 && who!=0x69 && who!=0x70) return false;

  writeReg(0x6B,0x01); // wake
  delay(20);
  writeReg(0x19,0x04); // 200 Hz
  writeReg(0x1A,0x03); // DLPF
  writeReg(0x1B,0x00); // gyro +/-250 dps
  writeReg(0x1C,0x00); // accel +/-2g
  return true;
}

static void calibrateGyro() {
  int64_t sx=0,sy=0,sz=0;
  int n=0;
  ImuSample s;
  for (int i=0;i<500;i++) {
    if (readImu(s)) { sx+=s.gx; sy+=s.gy; sz+=s.gz; n++; }
    delay(2);
  }
  if (n) {
    biasX=(float)sx/n;
    biasY=(float)sy/n;
    biasZ=(float)sz/n;
  }
}

// ---------------- APA106 custom RMT ----------------
static bool initLeds() {
  pinMode(PIN_LED_DATA,OUTPUT);
  digitalWrite(PIN_LED_DATA,LOW);
  if (!rmtInit(PIN_LED_DATA,RMT_TX_MODE,RMT_MEM_NUM_BLOCKS_1,10000000)) return false;
  rmtSetEOT(PIN_LED_DATA,0);
  return true;
}

static void showLeds(uint8_t brightness=55) {
  rmt_data_t symbols[LED_COUNT*24];
  size_t n=0;
  for (uint8_t i=0;i<LED_COUNT;i++) {
    uint8_t bytes[3]={
      (uint8_t)((uint16_t)leds[i].r*brightness/100U),
      (uint8_t)((uint16_t)leds[i].g*brightness/100U),
      (uint8_t)((uint16_t)leds[i].b*brightness/100U)
    };
    for (int c=0;c<3;c++) {
      for (int bit=7;bit>=0;bit--) {
        bool one=bytes[c]&(1U<<bit);
        symbols[n].level0=1;
        symbols[n].duration0=one?14:4;
        symbols[n].level1=0;
        symbols[n].duration1=one?4:14;
        n++;
      }
    }
  }
  rmtWrite(PIN_LED_DATA,symbols,n,RMT_WAIT_FOR_EVER);
  digitalWrite(PIN_LED_DATA,LOW);
  delayMicroseconds(100);
}

static uint8_t u8(float v) {
  return (uint8_t)constrain((int)lroundf(v),0,255);
}

static Rgb hsv(float h, float s, float v) {
  h=fmodf(h,360.0f);
  if (h<0) h+=360.0f;
  s=constrain(s,0.0f,1.0f);
  v=constrain(v,0.0f,1.0f);

  float c=v*s;
  float x=c*(1.0f-fabsf(fmodf(h/60.0f,2.0f)-1.0f));
  float m=v-c;
  float r=0,g=0,b=0;

  if (h<60)      {r=c;g=x;}
  else if(h<120) {r=x;g=c;}
  else if(h<180) {g=c;b=x;}
  else if(h<240) {g=x;b=c;}
  else if(h<300) {r=x;b=c;}
  else           {r=c;b=x;}

  return {u8((r+m)*255),u8((g+m)*255),u8((b+m)*255)};
}

static void addRgb(Rgb &dst, const Rgb &src, float gain=1.0f) {
  dst.r=(uint8_t)min(255,(int)dst.r+(int)(src.r*gain));
  dst.g=(uint8_t)min(255,(int)dst.g+(int)(src.g*gain));
  dst.b=(uint8_t)min(255,(int)dst.b+(int)(src.b*gain));
}

// physical order: top, right, bottom, left
static const float DIR_X[4]={0,1,0,-1};
static const float DIR_Y[4]={-1,0,1,0};

static void renderYoke(uint32_t nowMs) {
  // Treat X/Y tilt like a joystick/yoke.  The four physical bulbs are
  // TOP, RIGHT, BOTTOM, LEFT and light in the direction the rig is tilted.
  //
  // Diagonals naturally blend between two neighboring bulbs.  Direction also
  // changes color so the motion is readable even when brightness is similar:
  // TOP=cyan, RIGHT=red/orange, BOTTOM=magenta, LEFT=blue.
  // Installed board orientation: invert both axes so the lit side follows
  // the physical direction the stand is moved/tilted.
  // Use a broad 70-degree full-scale range so ordinary handling does not
  // instantly slam the output to maximum.
  float x=constrain(-tiltX/70.0f,-1.0f,1.0f); // invert X so its positive movement follows the upward physical direction
  float y=constrain(-tiltY/70.0f,-1.0f,1.0f); // Y already follows the upward physical direction
  float mag=constrain(sqrtf(x*x+y*y),0.0f,1.0f);

  // Soft blue idle on all four bulbs. Direction is communicated by WHICH
  // bulb changes, not by assigning each direction a different base color.
  for (int i=0;i<4;i++) leds[i]={0,18,42};

  const float deadZone=0.12f;
  if (mag < deadZone) return;

  // Remap the remaining travel to 0..1 and use a soft curve. This gives a
  // wide sensory range instead of jumping from dim straight to full.
  float active=(mag-deadZone)/(1.0f-deadZone);
  active=constrain(active,0.0f,1.0f);
  active=active*active*(3.0f-2.0f*active);

  // Dot product against each cardinal direction gives a smooth directional
  // weight.  Squaring makes the selected side feel more "joystick-like".
  const float vx[4]={0,1,0,-1};
  const float vy[4]={1,0,-1,0};
  const float activeHue=48.0f; // warm gold for every direction

  for (int i=0;i<4;i++) {
    float w=max(0.0f,x*vx[i]+y*vy[i]);
    w=w*w;

    // Keep inactive bulbs blue. As a direction becomes active, crossfade that
    // bulb from blue toward warm gold and increase its brightness.
    float strength=constrain(w*active,0.0f,1.0f);
    Rgb idle={0,18,42};
    Rgb hot=hsv(activeHue,0.92f,0.82f);

    leds[i].r=u8(idle.r*(1.0f-strength)+hot.r*strength);
    leds[i].g=u8(idle.g*(1.0f-strength)+hot.g*strength);
    leds[i].b=u8(idle.b*(1.0f-strength)+hot.b*strength);
  }

  // A fast shove/tilt gives the selected direction a brief brightness kick.
  if (motionEnergy>18.0f) {
    float kick=constrain((motionEnergy-18.0f)/55.0f,0.0f,0.18f);
    for (int i=0;i<4;i++) {
      float w=max(0.0f,x*vx[i]+y*vy[i]);
      if (w>0.0f) {
        Rgb boost=hsv(activeHue,0.65f,kick*w);
        addRgb(leds[i],boost,1.0f);
      }
    }
  }
}

static void renderFluid(uint32_t nowMs) {
  float tx=constrain(tiltY/45.0f,-1.0f,1.0f); // right/left physical field
  float ty=constrain(tiltX/45.0f,-1.0f,1.0f); // front/back physical field
  float tiltMag=constrain(sqrtf(tx*tx+ty*ty),0.0f,1.0f);

  // gyro Z continuously rolls the color palette while the object is moving
  hueSpin += gzDps*0.0025f;
  hueSpin=fmodf(hueSpin,360.0f);

  float baseHue=190.0f+hueSpin;
  float breath=0.55f+0.12f*sinf(nowMs*0.0022f);

  for (int i=0;i<4;i++) {
    float dot=tx*DIR_X[i]+ty*DIR_Y[i];
    float directional=0.5f+0.5f*dot;
    float v=(0.18f + 0.72f*directional*tiltMag + 0.22f*(1.0f-tiltMag))*breath;
    v += min(0.25f,motionEnergy*0.015f);

    float hue=baseHue + i*12.0f + gzDps*0.10f;
    leds[i]=hsv(hue,0.88f,constrain(v,0.0f,1.0f));
  }
}

static void renderComet(uint32_t nowMs) {
  float ax=constrain(tiltY/50.0f,-1.0f,1.0f);
  float ay=constrain(tiltX/50.0f,-1.0f,1.0f);
  float angle=atan2f(ay,ax); // -pi..pi
  float pos=(angle+PI)/(2.0f*PI)*4.0f;
  int head=((int)floorf(pos))&3;
  float frac=pos-floorf(pos);
  int next=(head+1)&3;
  int prev=(head+3)&3;

  float hue=30.0f+fmodf(hueSpin+nowMs*0.01f,300.0f);
  for(auto &p:leds) p={0,0,0};

  Rgb c=hsv(hue,0.95f,0.95f);
  addRgb(leds[head],c,1.0f-frac*0.45f);
  addRgb(leds[next],c,frac*0.85f);
  addRgb(leds[prev],c,0.18f+min(0.25f,motionEnergy*0.01f));

  hueSpin += gzDps*0.003f;
}

static void renderAurora(uint32_t nowMs) {
  float speed=min(1.0f,motionEnergy/35.0f);
  hueSpin += gzDps*0.0018f + speed*0.35f;
  for(int i=0;i<4;i++) {
    float phase=nowMs*0.0016f + i*1.25f + tiltX*0.025f - tiltY*0.018f;
    float wave=0.48f+0.35f*sinf(phase);
    float hue=145.0f + 100.0f*sinf(phase*0.57f+hueSpin*0.01f);
    leds[i]=hsv(hue,0.78f,constrain(wave+speed*0.25f,0.08f,1.0f));
  }
}

static void renderMotionLights(uint32_t nowMs) {
  if (mode==0) renderYoke(nowMs);
  else if (mode==1) renderFluid(nowMs);
  else if (mode==2) renderComet(nowMs);
  else renderAurora(nowMs);

  // YOKE is intended as an accessible sensory response: preserve the
  // directional color even during rough handling instead of washing all four
  // bulbs toward white. Other modes keep only a restrained warm motion pulse.
  if (mode!=0 && shakePulse>0.01f) {
    Rgb burst={120,72,28};
    for(auto &p:leds) addRgb(p,burst,shakePulse*0.18f);
  }
  shakePulse*=0.88f;

  showLeds(mode==0 ? 42 : 46);
}

// ---------------- tiny OLED text ----------------
static const uint8_t FONT5X7[16][5] PROGMEM={
 {0x3E,0x51,0x49,0x45,0x3E},{0x00,0x42,0x7F,0x40,0x00},{0x42,0x61,0x51,0x49,0x46},{0x21,0x41,0x45,0x4B,0x31},
 {0x18,0x14,0x12,0x7F,0x10},{0x27,0x45,0x45,0x45,0x39},{0x3C,0x4A,0x49,0x49,0x30},{0x01,0x71,0x09,0x05,0x03},
 {0x36,0x49,0x49,0x49,0x36},{0x06,0x49,0x49,0x29,0x1E},
 {0x7F,0x08,0x08,0x08,0x7F}, // H
 {0x7F,0x49,0x49,0x49,0x41}, // E
 {0x7F,0x40,0x40,0x40,0x40}, // L
 {0x3E,0x41,0x41,0x41,0x3E}, // O
 {0x7F,0x09,0x19,0x29,0x46}, // R
 {0x7F,0x02,0x0C,0x02,0x7F}  // M
};

static void oledCmd(uint8_t c){
  Wire.beginTransmission(OLED_ADDR); Wire.write(0x00); Wire.write(c); Wire.endTransmission();
}
static void oledChunk(const uint8_t *d,size_t len){
  while(len){
    size_t n=min((size_t)16,len);
    Wire.beginTransmission(OLED_ADDR); Wire.write(0x40);
    for(size_t i=0;i<n;i++) Wire.write(d[i]);
    Wire.endTransmission(); d+=n; len-=n;
  }
}
static bool initOled(){
  if(!i2cPresent(OLED_ADDR)) return false;
  const uint8_t seq[]={0xAE,0xD5,0x80,0xA8,0x3F,0xD3,0x00,0x40,0x8D,0x14,0x20,0x00,0xA1,0xC8,0xDA,0x12,0x81,0x7F,0xD9,0xF1,0xDB,0x40,0xA4,0xA6,0xAF};
  for(uint8_t b:seq) oledCmd(b);
  return true;
}
static void oledClear(){
  static uint8_t z[16]={0};
  oledCmd(0x21);oledCmd(0);oledCmd(127);oledCmd(0x22);oledCmd(0);oledCmd(7);
  for(int i=0;i<64;i++) oledChunk(z,16);
}

// Simple status uses serial as the authoritative diagnostic; OLED just gets
// a mode/activity bar to avoid carrying the full BloomGyro font table here.
static void oledStatus(){
  if(!i2cPresent(OLED_ADDR)) return;
  oledClear();
  uint8_t bar[16];
  for(int i=0;i<16;i++) bar[i]=(i<(mode+1)*4)?0x7E:0x00;
  oledCmd(0x21);oledCmd(16);oledCmd(31);oledCmd(0x22);oledCmd(2);oledCmd(2);
  oledChunk(bar,16);

  int level=(int)constrain(motionEnergy*0.45f,0.0f,16.0f);
  for(int i=0;i<16;i++) bar[i]=(i<level)?0x7E:0x00;
  oledCmd(0x21);oledCmd(16);oledCmd(31);oledCmd(0x22);oledCmd(5);oledCmd(5);
  oledChunk(bar,16);
}

// ---------------- touch mode button ----------------
static uint32_t touchBase=0;
static bool touchLatch=false;
static void initTouch(){
  uint64_t sum=0;
  for(int i=0;i<40;i++){sum+=touchRead(PIN_TOUCH);delay(5);}
  touchBase=(uint32_t)(sum/40ULL);
}
static void serviceTouch(){
  uint32_t v=touchRead(PIN_TOUCH);
  uint32_t th=touchBase+touchBase/5U;
  bool active=v>=th;
  if(active && !touchLatch){
    touchLatch=true;
    mode=(mode+1)%4;
    shakePulse=1.0f;
    Serial.printf("BML|MODE|%u\n",mode);
  } else if(!active){
    touchLatch=false;
    touchBase=(touchBase*127U+v)/128U;
  }
}

// ---------------- main ----------------
void setup(){
  Serial.begin(115200);
  delay(150);
  Serial.println("BML|IDENTITY|device=BloomMotionLights|fw=0.2.4|mode0=YOKE_BLUE_GOLD");

  Wire.begin(PIN_SDA,PIN_SCL,400000);
  bool ledOk=initLeds();
  bool imuOk=initImu();
  bool oledOk=initOled();

  Serial.printf("BML|BOOT|imu=%u|oled=%u|led=%u\n",imuOk,oledOk,ledOk);
  if(!imuOk) return;

  calibrateGyro();
  initTouch();
  lastSensorUs=micros();
}

void loop(){
  uint32_t nowUs=micros();
  uint32_t nowMs=millis();

  if((uint32_t)(nowUs-lastSensorUs)>=SENSOR_PERIOD_US){
    float dt=(nowUs-lastSensorUs)/1000000.0f;
    lastSensorUs=nowUs;
    dt=constrain(dt,0.001f,0.20f);

    ImuSample s;
    if(readImu(s)){
      float ax=(float)s.ax/ACC_SCALE;
      float ay=(float)s.ay/ACC_SCALE;
      float az=(float)s.az/ACC_SCALE;

      float rawTiltX=atan2f(ay,az)*180.0f/PI;
      float rawTiltY=atan2f(-ax,sqrtf(ay*ay+az*az))*180.0f/PI;
      tiltX=0.88f*tiltX+0.12f*rawTiltX;
      tiltY=0.88f*tiltY+0.12f*rawTiltY;

      gxDps=((float)s.gx-biasX)/GYRO_SCALE;
      gyDps=((float)s.gy-biasY)/GYRO_SCALE;
      gzDps=-((float)s.gz-biasZ)/GYRO_SCALE;

      float gyroMag=sqrtf(gxDps*gxDps+gyDps*gyDps+gzDps*gzDps);
      float accelMag=sqrtf(ax*ax+ay*ay+az*az);
      float impact=fabsf(accelMag-1.0f);

      float targetEnergy=min(80.0f,gyroMag*0.20f+impact*70.0f);
      motionEnergy=0.90f*motionEnergy+0.10f*targetEnergy;

      if(impact>0.75f || gyroMag>220.0f) shakePulse=1.0f;
    }
  }

  serviceTouch();

  if(nowMs-lastLedMs>=LED_PERIOD_MS){
    lastLedMs=nowMs;
    renderMotionLights(nowMs);
  }

  if(nowMs-lastOledMs>=OLED_PERIOD_MS){
    lastOledMs=nowMs;
    oledStatus();
    Serial.printf("BML|LIVE|mode=%u|x=%.1f|y=%.1f|gx=%.1f|gy=%.1f|gz=%.1f|energy=%.1f\n",
                  mode,tiltX,tiltY,gxDps,gyDps,gzDps,motionEnergy);
  }
}
