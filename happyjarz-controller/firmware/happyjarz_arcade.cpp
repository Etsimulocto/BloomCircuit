#include "happyjarz_arcade.h"

namespace {
constexpr int W=128, H=64;
HjArcadeDisplay d{};
bool active=false;
bool inGame=false;
uint8_t menuIndex=0;
uint8_t gameIndex=0;
uint32_t lastTick=0;
uint32_t nextTick=0;

const char *games[] = {
  "CATCH GLITTER",
  "GLITTER DODGE",
  "BLOOM SNAKE",
  "MEMORY SPARK",
  "JAR PONG",
  "METEOR TAP",
  "BLOOM RUNNER"
};
constexpr uint8_t GAME_COUNT=7;

void cls(){ if(d.clear) d.clear(); }
void px(int x,int y,bool on=true){ if(d.pixel && x>=0&&x<W&&y>=0&&y<H) d.pixel(x,y,on); }
void ln(int x0,int y0,int x1,int y1,bool on=true){ if(d.line) d.line(x0,y0,x1,y1,on); }
void rc(int x,int y,int w,int h,bool fill=false,bool on=true){ if(d.rect) d.rect(x,y,w,h,fill,on); }
void tx(int x,int y,const char*s,uint8_t size=1){ if(d.text) d.text(x,y,s,size); }
void show(){ if(d.present) d.present(); }
int clampi(int v,int lo,int hi){ return v<lo?lo:(v>hi?hi:v); }
uint32_t rnd(uint32_t n){ return n? (uint32_t)random((long)n):0; }

// ---------- shared helpers ----------
void drawHeader(const char *name,int score=0,int lives=-1){
  char b[24]; tx(0,0,name,1);
  if(score>=0){ snprintf(b,sizeof(b),"%d",score); tx(100,0,b,1); }
  if(lives>=0){ snprintf(b,sizeof(b),"L%d",lives); tx(78,0,b,1); }
  ln(0,8,127,8);
}

// ---------- game 0: Catch the Glitter ----------
struct CatchState { int slot=4; int score=0; int lives=3; int itemSlot=4; int itemY=12; bool bad=false; uint32_t fallMs=220; } catchS;
void resetCatch(){ catchS=CatchState(); catchS.itemSlot=rnd(10); catchS.bad=(rnd(7)==0); }
void spawnCatch(){ catchS.itemSlot=rnd(10); catchS.itemY=12; catchS.bad=(rnd(6)==0); }
void tickCatch(){
  catchS.itemY += 3;
  if(catchS.itemY>=56){
    if(catchS.itemSlot==catchS.slot){
      if(catchS.bad){ if(--catchS.lives<=0){ inGame=false; return; } }
      else catchS.score++;
    }
    spawnCatch();
  }
}
void inputCatch(HjArcadeButton b){ if(b==HJ_BTN_LEFT)catchS.slot=clampi(catchS.slot-1,0,9); if(b==HJ_BTN_RIGHT)catchS.slot=clampi(catchS.slot+1,0,9); }
void drawCatch(){ cls(); drawHeader("CATCH",catchS.score,catchS.lives); int x=8+catchS.slot*12; rc(x-5,56,11,5,false); int ix=8+catchS.itemSlot*12; if(catchS.bad){ln(ix-2,catchS.itemY-2,ix+2,catchS.itemY+2);ln(ix+2,catchS.itemY-2,ix-2,catchS.itemY+2);}else{ln(ix-2,catchS.itemY,ix+2,catchS.itemY);ln(ix,catchS.itemY-2,ix,catchS.itemY+2);} show(); }

// ---------- game 1: Glitter Dodge ----------
struct DodgeState { int slot=4; int score=0; int lives=3; int itemSlot=0; int itemY=12; uint32_t fallMs=180; } dodgeS;
void resetDodge(){ dodgeS=DodgeState(); dodgeS.itemSlot=rnd(10); }
void spawnDodge(){ dodgeS.itemSlot=rnd(10); dodgeS.itemY=12; }
void tickDodge(){ dodgeS.score++; dodgeS.itemY+=4; if(dodgeS.itemY>=55){ if(dodgeS.itemSlot==dodgeS.slot){ if(--dodgeS.lives<=0){inGame=false;return;} } spawnDodge(); } }
void inputDodge(HjArcadeButton b){ if(b==HJ_BTN_LEFT)dodgeS.slot=clampi(dodgeS.slot-1,0,9); if(b==HJ_BTN_RIGHT)dodgeS.slot=clampi(dodgeS.slot+1,0,9); if(b==HJ_BTN_A && dodgeS.itemY>45 && dodgeS.itemSlot==dodgeS.slot){ dodgeS.score+=25; spawnDodge(); } }
void drawDodge(){ cls(); drawHeader("DODGE",dodgeS.score,dodgeS.lives); int x=8+dodgeS.slot*12; rc(x-4,53,9,7,true); int ix=8+dodgeS.itemSlot*12; rc(ix-2,dodgeS.itemY-2,5,5,true); show(); }

// ---------- game 2: Bloom Snake ----------
struct SnakeState { int x[32]; int y[32]; int len=4; int dx=1,dy=0; int foodX=10,foodY=3; int score=0; } snakeS;
void resetSnake(){ snakeS=SnakeState(); for(int i=0;i<4;i++){snakeS.x[i]=7-i;snakeS.y[i]=3;} snakeS.foodX=rnd(16);snakeS.foodY=rnd(7); }
void tickSnake(){ int nx=(snakeS.x[0]+snakeS.dx+16)%16; int ny=(snakeS.y[0]+snakeS.dy+7)%7; for(int i=0;i<snakeS.len;i++) if(snakeS.x[i]==nx&&snakeS.y[i]==ny){inGame=false;return;} for(int i=snakeS.len;i>0;i--){snakeS.x[i]=snakeS.x[i-1];snakeS.y[i]=snakeS.y[i-1];} snakeS.x[0]=nx;snakeS.y[0]=ny; if(nx==snakeS.foodX&&ny==snakeS.foodY){ if(snakeS.len<31)snakeS.len++;snakeS.score++;snakeS.foodX=rnd(16);snakeS.foodY=rnd(7);} }
void inputSnake(HjArcadeButton b){ if(b==HJ_BTN_UP&&snakeS.dy!=1){snakeS.dx=0;snakeS.dy=-1;} if(b==HJ_BTN_DOWN&&snakeS.dy!=-1){snakeS.dx=0;snakeS.dy=1;} if(b==HJ_BTN_LEFT&&snakeS.dx!=1){snakeS.dx=-1;snakeS.dy=0;} if(b==HJ_BTN_RIGHT&&snakeS.dx!=-1){snakeS.dx=1;snakeS.dy=0;} }
void drawSnake(){ cls(); drawHeader("SNAKE",snakeS.score,-1); for(int i=0;i<snakeS.len;i++)rc(snakeS.x[i]*8,9+snakeS.y[i]*8,7,7,true); rc(snakeS.foodX*8+2,11+snakeS.foodY*8,3,3,true); show(); }

// ---------- game 3: Memory Spark ----------
struct MemoryState { uint8_t seq[32]; int len=1; int pos=0; int best=0; bool showing=true; int showPos=0; bool on=true; uint32_t phaseMs=0; } memS;
void resetMemory(){ memS=MemoryState(); memS.seq[0]=rnd(4); memS.phaseMs=millis()+450; }
void inputMemory(HjArcadeButton b){ if(memS.showing)return; int v=-1; if(b==HJ_BTN_UP)v=0; if(b==HJ_BTN_RIGHT)v=1; if(b==HJ_BTN_DOWN)v=2; if(b==HJ_BTN_LEFT)v=3; if(v<0)return; if(v!=memS.seq[memS.pos]){inGame=false;return;} memS.pos++; if(memS.pos>=memS.len){ memS.best=memS.len; if(memS.len<32)memS.seq[memS.len++]=rnd(4); memS.pos=0;memS.showing=true;memS.showPos=0;memS.on=true;memS.phaseMs=millis()+350; } }
void tickMemory(uint32_t now){ if(!memS.showing)return; if(now<memS.phaseMs)return; if(memS.on){memS.on=false;memS.phaseMs=now+180;}else{memS.showPos++; if(memS.showPos>=memS.len){memS.showing=false;memS.pos=0;}else{memS.on=true;memS.phaseMs=now+350;} } }
void drawArrow(int dir,bool lit){ int cx=64,cy=34; if(dir==0)cy=19; if(dir==1)cx=91; if(dir==2)cy=50; if(dir==3)cx=37; if(lit)rc(cx-7,cy-6,15,13,true); else rc(cx-7,cy-6,15,13,false); }
void drawMemory(){ cls(); drawHeader(memS.showing?"WATCH":"REPEAT",memS.len,-1); for(int i=0;i<4;i++)drawArrow(i,memS.showing&&memS.on&&memS.seq[memS.showPos]==i); show(); }

// ---------- game 4: Jar Pong ----------
struct PongState { int slot=4; int bx=64,by=28; int vx=2,vy=2; int rally=0; bool served=false; } pongS;
void resetPong(){ pongS=PongState(); }
void tickPong(){ if(!pongS.served)return; pongS.bx+=pongS.vx;pongS.by+=pongS.vy; if(pongS.bx<2||pongS.bx>125)pongS.vx=-pongS.vx; if(pongS.by<11)pongS.vy=abs(pongS.vy); int px=8+pongS.slot*12; if(pongS.by>=55){ if(abs(pongS.bx-px)<=9){pongS.vy=-abs(pongS.vy);pongS.rally++; pongS.vx=clampi(pongS.vx+(pongS.bx-px)/4,-5,5); if(pongS.vx==0)pongS.vx=1;}else{inGame=false;} } }
void inputPong(HjArcadeButton b){ if(b==HJ_BTN_LEFT)pongS.slot=clampi(pongS.slot-1,0,9); if(b==HJ_BTN_RIGHT)pongS.slot=clampi(pongS.slot+1,0,9); if(b==HJ_BTN_A&&!pongS.served)pongS.served=true; }
void drawPong(){ cls(); drawHeader("PONG",pongS.rally,-1); int pxv=8+pongS.slot*12; rc(pxv-8,58,17,3,true); rc(pongS.bx-1,pongS.by-1,3,3,true); show(); }

// ---------- game 5: Meteor Tap ----------
struct MeteorState { int slot=4;int meteorSlot=5;int y=12;int score=0;int lives=3;int streak=0; } meteorS;
void resetMeteor(){ meteorS=MeteorState();meteorS.meteorSlot=rnd(10); }
void spawnMeteor(){meteorS.meteorSlot=rnd(10);meteorS.y=12;}
void tickMeteor(){meteorS.y+=3+meteorS.streak/5;if(meteorS.y>60){meteorS.lives--;meteorS.streak=0;if(meteorS.lives<=0){inGame=false;return;}spawnMeteor();}}
void inputMeteor(HjArcadeButton b){if(b==HJ_BTN_LEFT)meteorS.slot=clampi(meteorS.slot-1,0,9);if(b==HJ_BTN_RIGHT)meteorS.slot=clampi(meteorS.slot+1,0,9);if(b==HJ_BTN_A){if(meteorS.slot==meteorS.meteorSlot&&abs(meteorS.y-48)<=7){int e=abs(meteorS.y-48);meteorS.score+=(e<=2?5:(e<=4?3:1));meteorS.streak++;spawnMeteor();}else{meteorS.lives--;meteorS.streak=0;if(meteorS.lives<=0)inGame=false;}}}
void drawMeteor(){cls();drawHeader("METEOR",meteorS.score,meteorS.lives);ln(0,48,127,48);int cx=8+meteorS.slot*12;ln(cx,45,cx,52);int mx=8+meteorS.meteorSlot*12;ln(mx-2,meteorS.y,mx+2,meteorS.y);ln(mx,meteorS.y-2,mx,meteorS.y+2);show();}

// ---------- game 6: Bloom Runner ----------
struct RunnerObj {int x=120;uint8_t lane=1;uint8_t kind=0;};
struct RunnerState {int lane=1;int px=20;int score=0;int jump=0;bool duck=false;RunnerObj o;} runS;
void resetRunner(){runS=RunnerState();runS.o.lane=rnd(3);runS.o.kind=rnd(3);}
void spawnRunner(){runS.o.x=127;runS.o.lane=rnd(3);runS.o.kind=rnd(3);}
void tickRunner(){runS.score++;if(runS.jump>0)runS.jump--;runS.o.x-=3;if(runS.o.x<runS.px-5)spawnRunner();if(abs(runS.o.x-runS.px)<=5&&runS.o.lane==runS.lane){if(runS.o.kind==2){runS.score+=20;spawnRunner();}else if(runS.o.kind==0){if(runS.jump==0){inGame=false;return;}spawnRunner();}else{if(!runS.duck){inGame=false;return;}spawnRunner();}}}
void inputRunner(HjArcadeButton b){if(b==HJ_BTN_UP)runS.lane=clampi(runS.lane-1,0,2);if(b==HJ_BTN_DOWN)runS.lane=clampi(runS.lane+1,0,2);if(b==HJ_BTN_LEFT)runS.px=clampi(runS.px-6,10,64);if(b==HJ_BTN_RIGHT)runS.px=clampi(runS.px+6,10,64);if(b==HJ_BTN_A&&runS.jump==0)runS.jump=7;if(b==HJ_BTN_B)runS.duck=true;}
void drawRunner(){cls();drawHeader("RUNNER",runS.score,-1);int ys[3]={24,40,56};for(int i=0;i<3;i++)ln(0,ys[i]+2,127,ys[i]+2);int py=ys[runS.lane]-(runS.jump?7:0);if(runS.duck)rc(runS.px-4,py-3,9,4,true);else rc(runS.px-2,py-10,5,10,true);int oy=ys[runS.o.lane];if(runS.o.kind==0)rc(runS.o.x-3,oy-5,7,6,true);else if(runS.o.kind==1)rc(runS.o.x-4,oy-12,9,3,true);else{ln(runS.o.x-2,oy-4,runS.o.x+2,oy-4);ln(runS.o.x,oy-6,runS.o.x,oy-2);}show();runS.duck=false;}

void resetSelected(){ gameIndex=menuIndex; inGame=true; lastTick=millis(); nextTick=lastTick+180; switch(gameIndex){case 0:resetCatch();break;case 1:resetDodge();break;case 2:resetSnake();break;case 3:resetMemory();break;case 4:resetPong();break;case 5:resetMeteor();break;case 6:resetRunner();break;} }
void inputGame(HjArcadeButton b){ if(b==HJ_BTN_HOME){inGame=false;return;} if(b==HJ_BTN_B && gameIndex!=6){inGame=false;return;} switch(gameIndex){case 0:inputCatch(b);break;case 1:inputDodge(b);break;case 2:inputSnake(b);break;case 3:inputMemory(b);break;case 4:inputPong(b);break;case 5:inputMeteor(b);break;case 6:inputRunner(b);break;} }
void tickGame(uint32_t now){ if(!inGame)return; if(gameIndex==3){tickMemory(now);return;} if(now<nextTick)return; uint32_t step=180; switch(gameIndex){case 0:tickCatch();step=150;break;case 1:tickDodge();step=120;break;case 2:tickSnake();step=190;break;case 4:tickPong();step=45;break;case 5:tickMeteor();step=110;break;case 6:tickRunner();step=90;break;} nextTick=now+step; }
void drawGame(){ if(!inGame)return; switch(gameIndex){case 0:drawCatch();break;case 1:drawDodge();break;case 2:drawSnake();break;case 3:drawMemory();break;case 4:drawPong();break;case 5:drawMeteor();break;case 6:drawRunner();break;} }

void drawMenu(){ cls(); tx(0,0,"HAPPY JARZ ARCADE",1); ln(0,8,127,8); for(int row=0;row<4;row++){int idx=(menuIndex+row)%GAME_COUNT;char b[22];snprintf(b,sizeof(b),"%c %s",row==0?'>':' ',games[idx]);tx(2,12+row*12,b,1);} tx(0,58,"A PLAY  B EXIT",1); show(); }
}

void hjArcadeBegin(const HjArcadeDisplay &display){ d=display; }
void hjArcadeEnter(){ active=true;inGame=false;menuIndex=0;drawMenu(); }
void hjArcadeExit(){ active=false;inGame=false; }
bool hjArcadeActive(){ return active; }
uint8_t hjArcadeMenuIndex(){ return menuIndex; }
const char *hjArcadeCurrentName(){ return inGame?games[gameIndex]:"ARCADE"; }

void hjArcadeButton(HjArcadeButton b){
  if(!active)return;
  if(inGame){ inputGame(b); if(!inGame)drawMenu(); return; }
  if(b==HJ_BTN_UP)menuIndex=(menuIndex+GAME_COUNT-1)%GAME_COUNT;
  else if(b==HJ_BTN_DOWN)menuIndex=(menuIndex+1)%GAME_COUNT;
  else if(b==HJ_BTN_A)resetSelected();
  else if(b==HJ_BTN_B||b==HJ_BTN_HOME){hjArcadeExit();return;}
  if(!inGame)drawMenu();
}

void hjArcadeService(uint32_t nowMs){
  if(!active)return;
  if(inGame){tickGame(nowMs); if(inGame)drawGame(); else drawMenu();}
}
