/*
  BloomOS v0.0.1 — HAPPY JARZ / BloomCircuit
  ESP32-S3 SuperMini reference rig

  Proven hardware:
    SH1106 128x64 OLED @ 0x3C
    SDA GPIO7 / SCL GPIO8
    HW-504 joystick: X GPIO4 / Y GPIO5 / SW GPIO6

  This first build is intentionally simple:
    - Bloom Core boot animation
    - Home menu
    - Joystick navigation
    - LAB screen
    - I2C scanner
    - Analog scope/readout
*/
#include <Wire.h>
#include <U8g2lib.h>
#include <math.h>

#define SDA_PIN 7
#define SCL_PIN 8
#define JOY_X 4
#define JOY_Y 5
#define JOY_SW 6

U8G2_SH1106_128X64_NONAME_F_HW_I2C core(U8G2_R0, U8X8_PIN_NONE);

enum Screen { HOME, LAB, I2C_SCAN, ANALOG_SCOPE };
Screen screen = HOME;
int selected = 0;
bool lastButton = HIGH;
unsigned long lastMove = 0;
float phase = 0;

const char* homeItems[] = {"BLOOM", "LAB", "TOOLS", "SETTINGS"};
const int homeCount = 4;
const char* labItems[] = {"I2C SCAN", "ANALOG", "INPUT TEST", "BACK"};
const int labCount = 4;

void drawBloom(float p) {
  int cx=64, cy=30, lx=cx, ly=cy;
  for(float t=0;t<18;t+=0.22){
    float r=t*1.35;
    float a=t+p;
    int x=cx+cos(a)*r;
    int y=cy+sin(a)*r*0.62;
    if(t>0.2) core.drawLine(lx,ly,x,y);
    lx=x; ly=y;
  }
  core.drawCircle(cx,cy,2);
}

void bootBloom() {
  for(int f=0;f<45;f++){
    core.clearBuffer();
    drawBloom(f*0.08);
    core.setFont(u8g2_font_5x8_tf);
    core.drawStr(42,62,"BloomOS");
    core.sendBuffer();
    delay(25);
  }
}

bool buttonPressed() {
  bool now=digitalRead(JOY_SW);
  bool hit=(lastButton==HIGH && now==LOW);
  lastButton=now;
  return hit;
}

int joyMove() {
  if(millis()-lastMove<180) return 0;
  int y=analogRead(JOY_Y);
  if(y<900){ lastMove=millis(); return -1; }
  if(y>3200){ lastMove=millis(); return 1; }
  return 0;
}

void drawList(const char* title, const char** items, int count) {
  core.clearBuffer();
  core.setFont(u8g2_font_6x12_tf);
  core.drawStr(0,10,title);
  core.drawHLine(0,13,128);
  core.setFont(u8g2_font_5x8_tf);
  for(int i=0;i<count;i++){
    int y=24+i*10;
    if(i==selected){
      core.drawBox(0,y-8,128,9);
      core.setDrawColor(0);
      core.drawStr(4,y,items[i]);
      core.setDrawColor(1);
    } else core.drawStr(4,y,items[i]);
  }
  core.sendBuffer();
}

void scanI2C() {
  core.clearBuffer();
  core.setFont(u8g2_font_6x12_tf);
  core.drawStr(0,10,"I2C SCAN");
  int y=25, found=0;
  core.setFont(u8g2_font_5x8_tf);
  for(byte a=1;a<127;a++){
    Wire.beginTransmission(a);
    if(Wire.endTransmission()==0){
      char buf[18];
      sprintf(buf,"FOUND 0x%02X",a);
      if(y<58) core.drawStr(4,y,buf);
      y+=10; found++;
    }
  }
  if(found==0) core.drawStr(4,25,"NO DEVICES");
  core.sendBuffer();
}

void drawAnalog() {
  int x=analogRead(JOY_X), y=analogRead(JOY_Y);
  core.clearBuffer();
  core.setFont(u8g2_font_6x12_tf);
  core.drawStr(0,10,"ANALOG SCOPE");
  core.setFont(u8g2_font_5x8_tf);
  char b[32];
  sprintf(b,"GPIO4 X: %4d",x); core.drawStr(4,28,b);
  sprintf(b,"GPIO5 Y: %4d",y); core.drawStr(4,40,b);
  core.drawFrame(4,49,120,10);
  int bar=map(x,0,4095,0,116);
  core.drawBox(6,51,bar,6);
  core.sendBuffer();
}

void setup() {
  Serial.begin(115200);
  pinMode(JOY_SW,INPUT_PULLUP);
  Wire.begin(SDA_PIN,SCL_PIN);
  core.setI2CAddress(0x3C*2);
  core.begin();
  bootBloom();
}

void loop() {
  int move=joyMove();
  bool click=buttonPressed();

  if(screen==HOME){
    if(move){ selected=(selected+move+homeCount)%homeCount; }
    if(click){
      if(selected==0){ phase+=0.8; }
      else if(selected==1){ screen=LAB; selected=0; }
    }
    drawList("BloomOS",homeItems,homeCount);
  }
  else if(screen==LAB){
    if(move){ selected=(selected+move+labCount)%labCount; }
    if(click){
      if(selected==0) screen=I2C_SCAN;
      else if(selected==1) screen=ANALOG_SCOPE;
      else if(selected==3){ screen=HOME; selected=0; }
    }
    drawList("LAB",labItems,labCount);
  }
  else if(screen==I2C_SCAN){
    scanI2C();
    if(click){ screen=LAB; selected=0; }
    delay(100);
  }
  else if(screen==ANALOG_SCOPE){
    drawAnalog();
    if(click){ screen=LAB; selected=1; }
    delay(40);
  }
}
