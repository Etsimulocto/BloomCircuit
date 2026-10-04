#include <Arduino.h>
#include "esp_system.h"
#include "esp_chip_info.h"
#include "esp_flash.h"

static const int TEST_PINS[] = {
  1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,21,
  33,34,35,36,37,38,39,40,41,45,46,47,48
};
static const int TEST_COUNT = sizeof(TEST_PINS)/sizeof(TEST_PINS[0]);

bool allowed(int pin){
  for(int i=0;i<TEST_COUNT;i++) if(TEST_PINS[i]==pin) return true;
  return false;
}
bool touchCap(int pin){ return pin>=1 && pin<=14; }
bool adcCap(int pin){ return pin>=1 && pin<=18; }

void emit(const String &s){ Serial.println(s); }
void emitKV(const char* kind,const String &rest){
  Serial.print("BBT|"); Serial.print(kind); Serial.print("|"); Serial.println(rest);
}

String gpioTest(int pin){
  int up=0,down=0;
  for(int i=0;i<5;i++){
    pinMode(pin,INPUT_PULLUP); delay(4); if(digitalRead(pin)==HIGH) up++;
    pinMode(pin,INPUT_PULLDOWN); delay(4); if(digitalRead(pin)==LOW) down++;
  }
  pinMode(pin,INPUT);
  String state=(up==5 && down==5)?"PASS":((up==0 || down==0)?"FAIL":"SUSPECT");
  emitKV("GPIO",state+"|pin="+pin+"|pullup="+up+"/5|pulldown="+down+"/5");
  return state;
}

void touchTest(int pin){
  if(!touchCap(pin)){ emitKV("MANUAL","NA|pin="+pin+"|op=TOUCH|reason=not_touch_capable"); return; }
  uint32_t mn=0xFFFFFFFF,mx=0; uint64_t sum=0;
  for(int i=0;i<16;i++){ uint32_t v=touchRead(pin); mn=min(mn,v); mx=max(mx,v); sum+=v; delay(5); }
  uint32_t avg=sum/16;
  String state=(avg==0 || avg==0xFFFFFFFF)?"SUSPECT":"PASS";
  emitKV("MANUAL",state+"|pin="+pin+"|op=TOUCH|avg="+avg+"|min="+mn+"|max="+mx);
}

void adcTest(int pin){
  if(!adcCap(pin)){ emitKV("MANUAL","NA|pin="+pin+"|op=ADC|reason=not_adc_capable"); return; }
  pinMode(pin,INPUT);
  int raw=analogRead(pin);
  emitKV("MANUAL","PASS|pin="+pin+"|op=ADC|raw="+raw);
}

void runAll(){
  int fail=0,suspect=0;
  emit("BBT|BEGIN|version=2.0|target=ESP32-S3-SuperMini");

  esp_chip_info_t chip; esp_chip_info(&chip);
  emitKV("CHIP",String(chip.cores>0?"PASS":"FAIL")+"|model=ESP32-S3|cores="+chip.cores+"|rev="+chip.revision+"|mhz="+getCpuFrequencyMhz());
  if(chip.cores<=0) fail++;

  uint32_t flash=0; esp_err_t fe=esp_flash_get_size(NULL,&flash);
  bool fok=(fe==ESP_OK && flash>0);
  emitKV("FLASH",String(fok?"PASS":"FAIL")+"|bytes="+flash);
  if(!fok) fail++;

  uint32_t heap=ESP.getFreeHeap();
  bool hok=heap>100000;
  emitKV("RAM",String(hok?"PASS":"FAIL")+"|free_heap="+heap+"|psram="+ESP.getPsramSize());
  if(!hok) fail++;

  esp_reset_reason_t rr=esp_reset_reason();
  bool bad=(rr==ESP_RST_PANIC || rr==ESP_RST_INT_WDT || rr==ESP_RST_TASK_WDT || rr==ESP_RST_WDT);
  emitKV("RESET",String(bad?"SUSPECT":"PASS")+"|reason="+(int)rr);
  if(bad) suspect++;

  for(int i=0;i<TEST_COUNT;i++){
    String s=gpioTest(TEST_PINS[i]);
    if(s=="FAIL") fail++; else if(s=="SUSPECT") suspect++;
  }

  emitKV("RESULT",String(fail?"FAIL":(suspect?"SUSPECT":"PASS"))+"|failures="+fail+"|suspects="+suspect);
  emit("BBT|END");
}

void manual(char op,int pin){
  if(!allowed(pin)){ emitKV("MANUAL","NA|pin="+pin+"|reason=not_exposed_profile_gpio"); return; }
  switch(op){
    case 'T': gpioTest(pin); break;
    case 'I':
      pinMode(pin,INPUT); delay(2);
      emitKV("MANUAL","PASS|pin="+pin+"|op=READ|value="+digitalRead(pin)); break;
    case 'U':
      pinMode(pin,INPUT_PULLUP); delay(3);
      emitKV("MANUAL",String(digitalRead(pin)==HIGH?"PASS":"FAIL")+"|pin="+pin+"|op=PULLUP|value="+digitalRead(pin)); break;
    case 'D':
      pinMode(pin,INPUT_PULLDOWN); delay(3);
      emitKV("MANUAL",String(digitalRead(pin)==LOW?"PASS":"FAIL")+"|pin="+pin+"|op=PULLDOWN|value="+digitalRead(pin)); break;
    case 'H':
      pinMode(pin,OUTPUT); digitalWrite(pin,HIGH); delay(2);
      emitKV("MANUAL","PASS|pin="+pin+"|op=DRIVE_HIGH|logic=3V3|external_verify_required=1"); break;
    case 'L':
      pinMode(pin,OUTPUT); digitalWrite(pin,LOW); delay(2);
      emitKV("MANUAL","PASS|pin="+pin+"|op=DRIVE_LOW|logic=0V|external_verify_required=1"); break;
    case 'Z':
      pinMode(pin,INPUT);
      emitKV("MANUAL","PASS|pin="+pin+"|op=RELEASE|mode=HIGH_Z"); break;
    case 'A': adcTest(pin); break;
    case 'C': touchTest(pin); break;
    default: emitKV("MANUAL","NA|pin="+pin+"|reason=unknown_command");
  }
}

void setup(){
  Serial.begin(115200);
  delay(1200);
  emit("BBT|READY|version=2.0");
}

void loop(){
  if(Serial.available()){
    String line=Serial.readStringUntil('\n');
    line.trim();
    if(line=="R"){ runAll(); return; }
    if(line.length()>=3 && line.charAt(1)==' '){
      char op=line.charAt(0);
      int pin=line.substring(2).toInt();
      manual(op,pin);
    }
  }
  delay(10);
}
