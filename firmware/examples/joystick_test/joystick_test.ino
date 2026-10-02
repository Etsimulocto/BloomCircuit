#define JOY_X 4
#define JOY_Y 5
#define JOY_SW 6
void setup(){Serial.begin(115200);delay(1000);pinMode(JOY_SW,INPUT_PULLUP);Serial.println("HAPPY JARZ JOYSTICK TEST");}
void loop(){int x=analogRead(JOY_X);int y=analogRead(JOY_Y);int b=digitalRead(JOY_SW);Serial.print("X: ");Serial.print(x);Serial.print("   Y: ");Serial.print(y);Serial.print("   BUTTON: ");Serial.println(b==LOW?"PRESSED":"UP");delay(250);}
