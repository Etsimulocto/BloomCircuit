#include <Arduino.h>
#include <esp_system.h>
#if !defined(CONFIG_IDF_TARGET_ESP32S3)
#error BloomFace requires ESP32-S3
#endif
constexpr int CLK_PIN=7, DT_PIN=8, SW_PIN=9;
portMUX_TYPE encoderMux=portMUX_INITIALIZER_UNLOCKED;
volatile int32_t quarters=0;
volatile uint8_t previousAB=0;
DRAM_ATTR const int8_t transitions[16]={0,-1,1,0,1,0,0,-1,-1,0,0,1,0,1,-1,0};
uint32_t taps=0,holds=0,session=0,lastSend=0,lastHost=0;
bool rawButton=true,stableButton=true,longSent=false;
uint32_t changedAt=0,pressedAt=0;
String command;
void ARDUINO_ISR_ATTR rotate(){
  uint8_t ab=(digitalRead(CLK_PIN)<<1)|digitalRead(DT_PIN);
  portENTER_CRITICAL_ISR(&encoderMux);
  quarters+=transitions[(previousAB<<2)|ab];previousAB=ab;
  portEXIT_CRITICAL_ISR(&encoderMux);
}
void report(const char* type){
  int32_t q;portENTER_CRITICAL(&encoderMux);q=quarters;portEXIT_CRITICAL(&encoderMux);
  Serial.printf("{\"type\":\"%s\",\"device\":\"BloomFace\",\"version\":\"0.1.0\",\"protocol\":1,\"session\":%lu,\"quarters\":%ld,\"taps\":%lu,\"holds\":%lu,\"button\":%s}\n",type,(unsigned long)session,(long)q,(unsigned long)taps,(unsigned long)holds,stableButton?"false":"true");
}
void setup(){
  Serial.begin(115200);command.reserve(40);session=esp_random();
  pinMode(CLK_PIN,INPUT_PULLUP);pinMode(DT_PIN,INPUT_PULLUP);pinMode(SW_PIN,INPUT_PULLUP);
  previousAB=(digitalRead(CLK_PIN)<<1)|digitalRead(DT_PIN);
  rawButton=stableButton=digitalRead(SW_PIN);
  if(!stableButton)pressedAt=millis();
  attachInterrupt(digitalPinToInterrupt(CLK_PIN),rotate,CHANGE);
  attachInterrupt(digitalPinToInterrupt(DT_PIN),rotate,CHANGE);
}
void loop(){
  while(Serial.available()){
    char c=Serial.read();
    if(c=='\n'){
      command.trim();
      if(command=="HELLO"){lastHost=millis();report("hello");}
      else if(command=="KEEP")lastHost=millis();
      command="";
    }else if(command.length()<40)command+=c;else command="";
  }
  uint32_t now=millis();bool b=digitalRead(SW_PIN);
  if(b!=rawButton){rawButton=b;changedAt=now;}
  if(now-changedAt>=25 && stableButton!=rawButton){
    stableButton=rawButton;
    if(!stableButton){pressedAt=now;longSent=false;}
    else if(!longSent){taps++;}
  }
  if(!stableButton && !longSent && now-pressedAt>=700){holds++;longSent=true;}
  // Only stream to an active host. This firmware never drives any GPIO output.
  if(now-lastHost<3000 && now-lastSend>=30){lastSend=now;report("input");}
  delay(1);
}
