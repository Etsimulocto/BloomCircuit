"""Pure face/control state, independent of UI and serial hardware."""
import random

MOODS=("CURIOUS", "SIDE EYE", "JOY", "SLEEPY", "PANIC", "GREMLIN", "VOID", "LOVESTRUCK", "STUBBORN", "MELTING", "DISCO", "SUSPICIOUS")
CONTROLS=("EXPRESSION", "GAZE", "ENERGY", "COLOR")


class FaceState:
    def __init__(self):
        self.mood=0; self.control=0; self.gaze=0.0; self.energy=0.45; self.hue=0.46
        self.reverse=False; self.detent=4; self.baseline=None; self.remainder=0
        self.surprise=0

    def turn(self, steps):
        if self.reverse: steps=-steps
        if self.control==0: self.mood=(self.mood+steps)%len(MOODS)
        elif self.control==1: self.gaze=max(-1.0,min(1.0,self.gaze+steps*0.12))
        elif self.control==2: self.energy=max(0.0,min(1.0,self.energy+steps*0.06))
        else: self.hue=(self.hue+steps*0.035)%1.0

    def tap(self): self.control=(self.control+1)%len(CONTROLS)

    def weird(self):
        self.mood=random.randrange(len(MOODS)); self.surprise+=1

    def ingest(self, record):
        current=tuple(record[k] for k in ("session","quarters","taps","holds"))
        if any(type(v) is not int for v in current): raise ValueError("Invalid encoder counters")
        if self.baseline is None or current[0]!=self.baseline[0]:
            self.baseline=current;self.remainder=0;return []
        old=self.baseline;self.baseline=current
        delta=current[1]-old[1]
        events=[]
        if abs(delta)>400: self.remainder=0  # reconnect/reset/corrupt counter
        else:
            self.remainder+=delta
            steps=int(self.remainder/self.detent)
            self.remainder-=steps*self.detent
            if steps:self.turn(steps);events.append(f"turn {steps}")
        for _ in range(min(10,max(0,current[2]-old[2]))):self.tap();events.append("tap")
        for _ in range(min(10,max(0,current[3]-old[3]))):self.weird();events.append("hold / weird burst")
        return events
