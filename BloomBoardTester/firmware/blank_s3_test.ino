#include <Arduino.h>
#include "esp_system.h"
#include "esp_chip_info.h"
#include "esp_flash.h"

static const int TEST_PINS[] = {1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,21};
static const int TEST_PIN_COUNT = sizeof(TEST_PINS)/sizeof(TEST_PINS[0]);
static const int TOUCH_PINS[] = {1,2,3,4,5,6,7,8,9,10,11,12,13,14};
static const int TOUCH_PIN_COUNT = sizeof(TOUCH_PINS)/sizeof(TOUCH_PINS[0]);

int failures = 0;
int suspects = 0;

void emit(const String &s){ Serial.println(s); }
void emitKV(const char* key, const String &value){ Serial.print("BBT|"); Serial.print(key); Serial.print("|"); Serial.println(value); }

void testChip(){
  esp_chip_info_t chip; esp_chip_info(&chip);
  bool ok = chip.cores > 0;
  emitKV("CHIP", String(ok?"PASS":"FAIL") + "|model=ESP32-S3|cores=" + chip.cores + "|rev=" + chip.revision + "|mhz=" + getCpuFrequencyMhz());
  if(!ok) failures++;
}

void testFlash(){
  uint32_t sz=0; esp_err_t e=esp_flash_get_size(NULL,&sz);
  bool ok=(e==ESP_OK && sz>0);
  emitKV("FLASH", String(ok?"PASS":"FAIL") + "|bytes=" + sz);
  if(!ok) failures++;
}

void testHeap(){
  uint32_t freeHeap=ESP.getFreeHeap();
  bool ok=freeHeap>100000;
  emitKV("RAM", String(ok?"PASS":"FAIL") + "|free_heap=" + freeHeap + "|psram=" + ESP.getPsramSize());
  if(!ok) failures++;
}

void testReset(){
  esp_reset_reason_t r=esp_reset_reason();
  bool bad=(r==ESP_RST_PANIC || r==ESP_RST_INT_WDT || r==ESP_RST_TASK_WDT || r==ESP_RST_WDT);
  emitKV("RESET", String(bad?"SUSPECT":"PASS") + "|reason=" + (int)r);
  if(bad) suspects++;
}

void testGPIO(int pin){
  int upPass=0, downPass=0;
  for(int i=0;i<5;i++){
    pinMode(pin, INPUT_PULLUP); delay(4); if(digitalRead(pin)==HIGH) upPass++;
    pinMode(pin, INPUT_PULLDOWN); delay(4); if(digitalRead(pin)==LOW) downPass++;
  }
  pinMode(pin, INPUT);
  String state="PASS";
  if(upPass==0 || downPass==0){ state="FAIL"; failures++; }
  else if(upPass<5 || downPass<5){ state="SUSPECT"; suspects++; }
  emitKV("GPIO", state + "|pin=" + pin + "|pullup=" + upPass + "/5|pulldown=" + downPass + "/5");
}

void testTouch(int pin){
  uint32_t mn=0xFFFFFFFF, mx=0; uint64_t sum=0;
  const int N=16;
  for(int i=0;i<N;i++){
    uint32_t v=touchRead(pin); mn=min(mn,v); mx=max(mx,v); sum+=v; delay(5);
  }
  uint32_t avg=sum/N;
  String state=(avg==0 || avg==0xFFFFFFFF)?"SUSPECT":"PASS";
  if(state=="SUSPECT") suspects++;
  emitKV("TOUCH", state + "|pin=" + pin + "|avg=" + avg + "|min=" + mn + "|max=" + mx);
}

void runTests(){
  failures=0; suspects=0;
  emit("BBT|BEGIN|version=1.0|target=ESP32-S3-SuperMini");
  testChip();
  testFlash();
  testHeap();
  testReset();
  for(int i=0;i<TEST_PIN_COUNT;i++) testGPIO(TEST_PINS[i]);
  for(int i=0;i<TOUCH_PIN_COUNT;i++) testTouch(TOUCH_PINS[i]);
  String result = failures ? "FAIL" : (suspects ? "SUSPECT" : "PASS");
  emitKV("RESULT", result + "|failures=" + failures + "|suspects=" + suspects);
  emit("BBT|END");
}

void setup(){
  Serial.begin(115200);
  delay(1500);
  runTests();
}

void loop(){
  if(Serial.available()){
    char c=Serial.read();
    if(c=='R' || c=='r') runTests();
  }
  delay(10);
}
