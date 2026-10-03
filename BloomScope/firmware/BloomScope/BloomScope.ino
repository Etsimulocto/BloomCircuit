#include <Arduino.h>
#if !defined(CONFIG_IDF_TARGET_ESP32S3)
#error BloomScope requires ESP32-S3
#endif

// Proposed bench map, independent of HAPPY JARZ firmware. Verify board labels.
constexpr int ADC_PIN=1, CONT_PIN=2, DRIVE_PIN=12, BEEP_PIN=11;
const int logicPins[]={7,8,9,10}, touchPins[]={4,5,6};
const char* modes[]={"METER","PWM","SCOPE","LOGIC","CONT"};
int mode=0; bool running=false, muted=false, touchEnabled=false;
uint32_t baseline[3]={}; bool held[3]={};
uint32_t lastHost=0,lastReport=0,lastTouch=0;
String command;
volatile uint32_t rise=0,period=0,highTime=0,lastEdge=0;
portMUX_TYPE mux=portMUX_INITIALIZER_UNLOCKED;
void ARDUINO_ISR_ATTR edge(){
  uint32_t now=micros(); bool high=digitalRead(logicPins[0]);
  portENTER_CRITICAL_ISR(&mux);
  if(high){ if(rise) period=now-rise; rise=now; }
  else if(rise) highTime=now-rise;
  lastEdge=now;
  portEXIT_CRITICAL_ISR(&mux);
}
void quiet(){pinMode(DRIVE_PIN,INPUT); noTone(BEEP_PIN);}
void state(){Serial.printf("{\"type\":\"state\",\"mode\":\"%s\",\"running\":%s,\"muted\":%s}\n",modes[mode],running?"true":"false",muted?"true":"false");}
void hello(){Serial.println("{\"type\":\"hello\",\"device\":\"BloomScope\",\"version\":\"0.1.0\",\"protocol\":1}");state();}
void calibrate(){
  for(int j=0;j<3;j++){uint64_t sum=0; for(int i=0;i<16;i++)sum+=touchRead(touchPins[j]); baseline[j]=sum/16; held[j]=false;}
}
void handle(String c){
  c.trim();
  if(c=="HELLO"){lastHost=millis();hello();return;}
  if(c=="KEEP"){lastHost=millis();return;}
  if(c=="STOP"){running=false;quiet();}
  else if(c=="START"){if(mode!=4)running=true;}
  else if(c=="ARM CONT"){quiet();mode=4;running=true;pinMode(DRIVE_PIN,OUTPUT);digitalWrite(DRIVE_PIN,HIGH);}
  else if(c.startsWith("MODE ")){
    bool found=false;for(int i=0;i<4;i++)if(c.substring(5)==modes[i]){quiet();mode=i;found=true;break;}
    if(!found){Serial.println("{\"type\":\"error\",\"message\":\"Unknown mode; continuity requires ARM CONT\"}");return;}
  }
  else if(c=="TOUCH ON"){calibrate();touchEnabled=true;}
  else if(c=="TOUCH OFF"){touchEnabled=false;}
  else if(c=="CAL TOUCH"){calibrate();}
  else if(c=="MUTE"){muted=!muted;if(muted)noTone(BEEP_PIN);}
  else{Serial.println("{\"type\":\"error\",\"message\":\"Unknown command\"}");return;}
  lastHost=millis();state();
}
void capture(){
  constexpr int N=128; uint32_t times[N]; uint16_t values[N];
  uint32_t start=micros(),next=start;
  for(int i=0;i<N;i++){
    while((int32_t)(micros()-next)<0){}
    times[i]=micros()-start;
    if(mode==2)values[i]=analogReadMilliVolts(ADC_PIN);
    else{values[i]=0;for(int j=0;j<4;j++)values[i]|=digitalRead(logicPins[j])<<j;}
    next+=1000;
  }
  Serial.printf("{\"type\":\"capture\",\"mode\":\"%s\",\"t_us\":[",modes[mode]);
  for(int i=0;i<N;i++){if(i)Serial.print(',');Serial.print(times[i]);}
  Serial.print("],\"values\":[");
  for(int i=0;i<N;i++){if(i)Serial.print(',');Serial.print(values[i]);}
  Serial.println("]}");
}
void setup(){
  Serial.begin(115200);command.reserve(80);quiet();
  analogReadResolution(12);analogSetPinAttenuation(ADC_PIN,ADC_11db);analogSetPinAttenuation(CONT_PIN,ADC_11db);
  for(int p:logicPins)pinMode(p,INPUT_PULLDOWN);
  attachInterrupt(digitalPinToInterrupt(logicPins[0]),edge,CHANGE);
  lastHost=millis();
}
void loop(){
  while(Serial.available()){
    char c=Serial.read();if(c=='\n'){handle(command);command="";}
    else if(command.length()<80)command+=c;
    else{command="";running=false;quiet();}
  }
  if(running && millis()-lastHost>3000){running=false;quiet();state();}
  if(touchEnabled && millis()-lastTouch>100){
    lastTouch=millis();
    for(int i=0;i<3;i++){
      uint32_t v=touchRead(touchPins[i]);bool hit=baseline[i]>0 && v>baseline[i]*1.5;
      if(hit && !held[i]){
        if(i==0){quiet();mode=(mode+1)%4;}
        if(i==1){if(mode!=4)running=!running;else{running=false;quiet();}}
        if(i==2){muted=!muted;if(muted)noTone(BEEP_PIN);}
        state();
      }held[i]=hit;
    }
  }
  if(!running || millis()-lastReport<150){delay(1);return;}
  lastReport=millis();
  if(mode==2 || mode==3){capture();return;}
  if(mode==0){uint32_t sum=0;for(int i=0;i<16;i++)sum+=analogReadMilliVolts(ADC_PIN);
    Serial.printf("{\"type\":\"meter\",\"adc_mv\":%lu}\n",(unsigned long)(sum/16));}
  if(mode==1){uint32_t p,h,e;portENTER_CRITICAL(&mux);p=period;h=highTime;e=lastEdge;portEXIT_CRITICAL(&mux);
    bool valid=p && h<=p && micros()-e<1000000;
    Serial.printf("{\"type\":\"pwm\",\"valid\":%s,\"period_us\":%lu,\"high_us\":%lu,\"state\":%d}\n",valid?"true":"false",(unsigned long)p,(unsigned long)h,digitalRead(logicPins[0]));}
  if(mode==4){uint32_t mv=analogReadMilliVolts(CONT_PIN);bool closed=mv<35;
    if(closed && !muted)tone(BEEP_PIN,2400);else noTone(BEEP_PIN);
    Serial.printf("{\"type\":\"continuity\",\"closed\":%s,\"mv\":%lu}\n",closed?"true":"false",(unsigned long)mv);}
}
