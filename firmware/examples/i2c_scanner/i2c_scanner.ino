#include <Wire.h>
#define SDA_PIN 7
#define SCL_PIN 8
void setup(){Serial.begin(115200);delay(1000);Wire.begin(SDA_PIN,SCL_PIN);Serial.println("Scanning I2C...");for(byte a=1;a<127;a++){Wire.beginTransmission(a);if(Wire.endTransmission()==0){Serial.print("FOUND DEVICE: 0x");if(a<16)Serial.print("0");Serial.println(a,HEX);}}Serial.println("Scan finished.");}
void loop(){}
