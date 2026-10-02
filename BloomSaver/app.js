(() => {
  'use strict';

  const canvas = document.getElementById('stage');
  const ctx = canvas.getContext('2d', { alpha: false });
  const panel = document.getElementById('panel');
  const controlsEl = document.getElementById('controls');
  const fpsEl = document.getElementById('fps');
  const seedLabel = document.getElementById('seedLabel');
  const seedInput = document.getElementById('seed');
  const presetList = document.getElementById('presetList');
  const presetName = document.getElementById('presetName');
  const showPanel = document.getElementById('showPanel');

  const SYMBOLS = [
    '!', '@', '#', '$', '%', '^', '&', '*', '(', ')', '-', '_', '+', '=',
    '[', ']', '{', '}', '<', '>', '/', '\\', '|', ':', ';', '?', '~', '`',
    '.', ',', '"', "'", '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
    'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N',
    'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z',
    'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'm', 'n', 'o',
    'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z',
    '★', '☆', '✦', '✧', '✶', '✷', '✹', '✺', '✸', '✳', '✴', '✵',
    '◆', '◇', '◈', '◊', '●', '○', '◉', '◎', '◍', '◌', '◐', '◑',
    '▲', '△', '▼', '▽', '◀', '◁', '▶', '▷',
    '■', '□', '▪', '▫', '▣', '▤', '▥', '▦', '▧', '▨', '▩',
    '×', '÷', '±', '∞', '≈', '≠', '≤', '≥', '∑', '∆', '√', '∴', '∵',
    '←', '→', '↑', '↓', '↖', '↗', '↘', '↙', '↔', '↕',
    '☀', '☼', '☾', '☽', '☁', '☄', '☊', '☋', '☯',
    '♠', '♣', '♥', '♦', '♪', '♫', '♩', '♬',
    '⌁', '⌘', '⌬', '⌖', '⌂', '⌑', '⌗', '⌁',
    '░', '▒', '▓', '█', '▚', '▞', '╳', '╱', '╲',
    '─', '│', '┌', '┐', '└', '┘', '├', '┤', '┬', '┴', '┼',
    '≋', '≡', '⊕', '⊗', '⊙', '⊛', '⊞', '⊠', '⊿', '⌁'
  ];

  const schema = {
    count:{label:'Glitter count',min:40,max:1200,step:1,value:420},
    emitters:{label:'Emitters',min:1,max:12,step:1,value:4},
    attractors:{label:'Attractors',min:0,max:10,step:1,value:3},
    repulsors:{label:'Repulsors',min:0,max:8,step:1,value:1},
    speed:{label:'Speed',min:.05,max:3,step:.01,value:.75},
    drift:{label:'Drift',min:0,max:3,step:.01,value:.7},
    swirl:{label:'Swirl',min:-3,max:3,step:.01,value:.8},
    noise:{label:'Field noise',min:0,max:3,step:.01,value:.9},
    attraction:{label:'Attraction',min:0,max:3,step:.01,value:.8},
    repulsion:{label:'Repulsion',min:0,max:3,step:.01,value:.7},
    burst:{label:'Burst chance',min:0,max:1,step:.01,value:.28},
    trails:{label:'Trails',min:0,max:.97,step:.01,value:.82},
    glow:{label:'Glow',min:0,max:40,step:1,value:20},
    twinkle:{label:'Twinkle',min:0,max:3,step:.01,value:1.1},
    sizeMin:{label:'Size min',min:.2,max:8,step:.1,value:.7},
    sizeMax:{label:'Size max',min:1,max:24,step:.1,value:4.2},
    symbolChance:{label:'Symbol chance',min:0,max:1,step:.01,value:.28},
    hue:{label:'Glitter hue',min:0,max:360,step:1,value:42},
    hueSpread:{label:'Hue spread',min:0,max:180,step:1,value:145},
    bgSpeed:{label:'Background fade speed',min:2,max:60,step:1,value:18},
    bgSaturation:{label:'Background saturation',min:0,max:100,step:1,value:46},
    bgBrightness:{label:'Background brightness',min:1,max:35,step:1,value:11}
  };

  let settings = Object.fromEntries(Object.entries(schema).map(([k,v]) => [k,v.value]));
  let seed = Math.floor(Math.random()*1e9);
  let rng = mulberry32(seed);
  let particles = [];
  let emitters = [];
  let wells = [];
  let running = true;
  let last = performance.now();
  let fpsStamp = last;
  let fpsFrames = 0;
  let lastActivity = last;
  let idleHidden = false;
  let width = innerWidth;
  let height = innerHeight;
  let dpr = Math.min(devicePixelRatio || 1, 2);
  let bg = {a:rnd(0,360), b:rnd(0,360), c:rnd(0,360), next:rnd(0,360), stamp:last};

  function mulberry32(a){
    return function(){
      let t = a += 0x6D2B79F5;
      t = Math.imul(t ^ t >>> 15, t | 1);
      t ^= t + Math.imul(t ^ t >>> 7, t | 61);
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }

  function rnd(a=0,b=1){ return a + (b-a) * (rng ? rng() : Math.random()); }
  function chance(p){ return rnd() < p; }
  function pick(a){ return a[Math.floor(rnd(0,a.length))]; }
  function clamp(v,a,b){ return Math.max(a, Math.min(b,v)); }
  function fmt(v){ return Math.abs(v-Math.round(v)) < .001 ? String(Math.round(v)) : v.toFixed(2); }

  function resize(){
    width = innerWidth;
    height = innerHeight;
    dpr = Math.min(devicePixelRatio || 1, 2);
    canvas.width = Math.floor(width*dpr);
    canvas.height = Math.floor(height*dpr);
    canvas.style.width = width + 'px';
    canvas.style.height = height + 'px';
    ctx.setTransform(dpr,0,0,dpr,0,0);
    ctx.fillStyle = '#03040a';
    ctx.fillRect(0,0,width,height);
    reconcile();
  }

  function buildControls(){
    controlsEl.innerHTML = '';
    for(const [key,s] of Object.entries(schema)){
      const w = document.createElement('div');
      w.className = 'control';
      w.innerHTML = `<div class="control-head"><span>${s.label}</span><output data-out="${key}">${fmt(settings[key])}</output></div><input data-key="${key}" type="range" min="${s.min}" max="${s.max}" step="${s.step}" value="${settings[key]}">`;
      w.querySelector('input').addEventListener('input',e=>{
        settings[key] = Number(e.target.value);
        w.querySelector('output').value = fmt(settings[key]);
        reconcile();
        touch();
      });
      controlsEl.appendChild(w);
    }
  }

  function sync(){
    document.querySelectorAll('[data-key]').forEach(el => el.value = settings[el.dataset.key]);
    document.querySelectorAll('[data-out]').forEach(el => el.value = fmt(settings[el.dataset.out]));
    seedInput.value = seed;
    seedLabel.textContent = `SEED ${seed}`;
  }

  function newEmitter(){
    const edge = pick(['left','right','top','bottom','corner','random','center']);
    let x = rnd(0,width), y = rnd(0,height), angle = rnd(0,Math.PI*2);
    if(edge==='left'){x=-20;angle=rnd(-.8,.8);}
    if(edge==='right'){x=width+20;angle=Math.PI+rnd(-.8,.8);}
    if(edge==='top'){y=-20;angle=Math.PI/2+rnd(-.8,.8);}
    if(edge==='bottom'){y=height+20;angle=-Math.PI/2+rnd(-.8,.8);}
    if(edge==='corner'){
      const q = pick([[0,0],[width,0],[0,height],[width,height]]);
      x=q[0]; y=q[1];
      angle=Math.atan2(height/2-y,width/2-x)+rnd(-1,1);
    }
    if(edge==='center'){x=width/2+rnd(-80,80);y=height/2+rnd(-80,80);}
    return {x,y,angle,spread:rnd(.15,1.4),power:rnd(.4,2.8),rate:rnd(.3,1.2),motion:pick(['wander','orbit','figure8','spiral','edge']),phase:rnd(0,Math.PI*2),radius:rnd(40,Math.min(width,height)*.42),vx:rnd(-.25,.25),vy:rnd(-.25,.25),age:0,life:rnd(7000,26000)};
  }

  function newWell(rep=false){
    return {x:rnd(0,width),y:rnd(0,height),vx:rnd(-.25,.25),vy:rnd(-.25,.25),strength:(rep?-1:1)*rnd(.3,1.5),radius:rnd(80,320),motion:pick(['wander','orbit','figure8','spiral','edge']),phase:rnd(0,Math.PI*2),radius2:rnd(40,260),age:0,life:rnd(9000,30000)};
  }

  function reconcile(){
    while(emitters.length < settings.emitters) emitters.push(newEmitter());
    while(emitters.length > settings.emitters) emitters.pop();
    const want = Math.max(0,settings.attractors+settings.repulsors);
    while(wells.length < want){
      const rep = wells.filter(w=>w.strength<0).length < settings.repulsors;
      wells.push(newWell(rep));
    }
    while(wells.length > want) wells.pop();
    let reps = wells.filter(w=>w.strength<0).length;
    for(const w of wells){
      if(reps < settings.repulsors && w.strength > 0){ w.strength = -Math.abs(w.strength); reps++; }
      else if(reps > settings.repulsors && w.strength < 0){ w.strength = Math.abs(w.strength); reps--; }
    }
  }

  function moveActor(a,t,dt){
    a.age += dt;
    const r = a.radius2 || a.radius;
    const q = t*.00012 + a.phase;
    if(a.motion==='wander'){
      a.vx += Math.sin(t*.00031+a.phase)*.006;
      a.vy += Math.cos(t*.00027+a.phase*1.3)*.006;
      a.vx = clamp(a.vx,-.8,.8);
      a.vy = clamp(a.vy,-.8,.8);
      a.x += a.vx*dt*.06;
      a.y += a.vy*dt*.06;
    } else if(a.motion==='orbit'){
      a.x = width/2 + Math.cos(q)*r;
      a.y = height/2 + Math.sin(q)*r*.68;
    } else if(a.motion==='figure8'){
      a.x = width/2 + Math.sin(q)*r;
      a.y = height/2 + Math.sin(q*2)*r*.45;
    } else if(a.motion==='spiral'){
      const rr = r*(.35+.6*((Math.sin(t*.00006+a.phase)+1)/2));
      a.x = width/2 + Math.cos(q)*rr;
      a.y = height/2 + Math.sin(q)*rr;
    } else if(a.motion==='edge'){
      const p=((t*.000025+a.phase/(Math.PI*2))%1+1)%1;
      const per=2*(width+height);
      const d=p*per;
      if(d<width){a.x=d;a.y=0;}
      else if(d<width+height){a.x=width;a.y=d-width;}
      else if(d<2*width+height){a.x=width-(d-width-height);a.y=height;}
      else{a.x=0;a.y=height-(d-2*width-height);}
    }
    if(a.x<-100)a.x=width+100;
    if(a.x>width+100)a.x=-100;
    if(a.y<-100)a.y=height+100;
    if(a.y>height+100)a.y=-100;
    if(a.age>a.life) Object.assign(a,a.strength===undefined?newEmitter():newWell(a.strength<0));
  }

  function spawn(e,burst=false){
    if(particles.length >= settings.count) return;
    const a = e.angle + rnd(-e.spread,e.spread);
    const v = e.power*rnd(.4,1.7)*(burst?rnd(1.4,2.8):1);
    const lo = Math.min(settings.sizeMin,settings.sizeMax);
    const hi = Math.max(settings.sizeMin,settings.sizeMax);
    const isSymbol = chance(settings.symbolChance);
    const shape = isSymbol ? 'symbol' : pick(['dot','diamond','cross','dash','shard']);
    particles.push({x:e.x,y:e.y,px:e.x,py:e.y,vx:Math.cos(a)*v,vy:Math.sin(a)*v,size:rnd(lo,hi),age:0,life:rnd(3000,12000),shape,glyph:isSymbol ? pick(SYMBOLS) : '',hue:(settings.hue+rnd(-settings.hueSpread,settings.hueSpread)+360)%360,alpha:rnd(.45,1),twinkle:rnd(.5,2.6),spin:rnd(-.1,.1),angle:rnd(0,Math.PI*2)});
  }

  function burst(){
    const e = newEmitter();
    e.x = rnd(0,width);
    e.y = rnd(0,height);
    e.spread = rnd(.8,Math.PI);
    e.power = rnd(1.5,4);
    for(let i=0;i<Math.round(rnd(18,90));i++) spawn(e,true);
  }

  function updateBackground(t){
    const seconds=Math.max(2,settings.bgSpeed)*1000;
    const phase=clamp((t-bg.stamp)/seconds,0,1);
    if(phase>=1){bg.a=bg.b;bg.b=bg.c;bg.c=bg.next;bg.next=rnd(0,360);bg.stamp=t;}
    const p=(t-bg.stamp)/seconds;
    const h1=(bg.a+(bg.b-bg.a)*p+360)%360;
    const h2=(bg.c+(bg.next-bg.c)*p+360)%360;
    const s=settings.bgSaturation;
    const l=settings.bgBrightness;
    const g=ctx.createLinearGradient(0,0,width,height);
    g.addColorStop(0,`hsl(${h1} ${s}% ${l}%)`);
    g.addColorStop(1,`hsl(${h2} ${Math.max(0,s-8)}% ${Math.max(1,l-3)}%)`);
    ctx.fillStyle=g;
    ctx.fillRect(0,0,width,height);
  }

  function fadeOverlay(){
    ctx.save();
    ctx.fillStyle=`rgba(0,0,0,${1-settings.trails})`;
    ctx.fillRect(0,0,width,height);
    ctx.restore();
  }

  function drawParticle(p,t){
    const shimmer=.3+.7*Math.abs(Math.sin(t*.0012*settings.twinkle*p.twinkle+p.angle));
    const alpha=clamp(p.alpha*(1-p.age/p.life)*(.6+.5*shimmer),0,1);
    const c=`hsla(${p.hue},94%,72%,${alpha})`;
    const s=p.size*(.8+.35*shimmer);
    ctx.save();
    ctx.translate(p.x,p.y);
    ctx.rotate(p.angle);
    ctx.fillStyle=c;
    ctx.strokeStyle=c;
    ctx.shadowColor=c;
    ctx.shadowBlur=settings.glow*(.25+.8*shimmer);
    if(p.shape==='symbol'){
      ctx.font=`700 ${Math.max(6,s*1.8)}px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace`;
      ctx.textAlign='center';
      ctx.textBaseline='middle';
      ctx.fillText(p.glyph,0,0);
    } else if(p.shape==='diamond'){
      ctx.beginPath();ctx.moveTo(0,-s*1.5);ctx.lineTo(s*.75,0);ctx.lineTo(0,s*1.5);ctx.lineTo(-s*.75,0);ctx.closePath();ctx.fill();
    } else if(p.shape==='cross'){
      ctx.lineWidth=Math.max(.5,s*.2);ctx.beginPath();ctx.moveTo(-s,0);ctx.lineTo(s,0);ctx.moveTo(0,-s);ctx.lineTo(0,s);ctx.stroke();
    } else if(p.shape==='dash'){
      ctx.fillRect(-s*1.3,-s*.18,s*2.6,s*.36);
    } else if(p.shape==='shard'){
      ctx.beginPath();ctx.moveTo(-s*.35,-s);ctx.lineTo(s*.6,-s*.15);ctx.lineTo(s*.12,s);ctx.closePath();ctx.fill();
    } else {
      ctx.beginPath();ctx.arc(0,0,Math.max(.4,s*.5),0,Math.PI*2);ctx.fill();
    }
    ctx.restore();
  }

  function randomize(){
    seed=Math.floor(Math.random()*1e9);
    rng=mulberry32(seed);
    settings={...settings,count:Math.round(rnd(180,900)),emitters:Math.round(rnd(2,9)),attractors:Math.round(rnd(0,7)),repulsors:Math.round(rnd(0,4)),speed:rnd(.25,1.8),drift:rnd(.1,2.2),swirl:rnd(-2.4,2.4),noise:rnd(.1,2.3),attraction:rnd(.1,2),repulsion:rnd(.1,2),burst:rnd(.05,.6),trails:rnd(.55,.94),glow:rnd(5,32),twinkle:rnd(.2,2.4),sizeMin:rnd(.2,3),sizeMax:rnd(4,24),symbolChance:rnd(.08,.72),hue:rnd(0,360),hueSpread:rnd(20,180),bgSpeed:rnd(8,40),bgSaturation:rnd(20,75),bgBrightness:rnd(5,22)};
    particles=[];emitters=[];wells=[];
    bg={a:rnd(0,360),b:rnd(0,360),c:rnd(0,360),next:rnd(0,360),stamp:performance.now()};
    reconcile();sync();
  }

  function mutate(){
    for(const [k,s] of Object.entries(schema)){
      if(chance(.55)){
        const span=s.max-s.min;
        settings[k]=clamp(settings[k]+rnd(-.12,.12)*span,s.min,s.max);
        if(s.step>=1)settings[k]=Math.round(settings[k]);
      }
    }
    seed=(seed+Math.floor(rnd(1,999983)))>>>0;
    rng=mulberry32(seed);
    sync();reconcile();
  }

  function state(){return{version:4,seed,settings:{...settings}};}
  function loadState(s){if(!s)return;seed=Number(s.seed)||seed;rng=mulberry32(seed);settings={...settings,...s.settings};particles=[];emitters=[];wells=[];reconcile();sync();}
  function presets(){try{return JSON.parse(localStorage.getItem('bloomsaver.glitter.presets')||'{}')}catch{return{}}}
  function refreshPresets(){const p=presets();presetList.innerHTML='<option value="">Saved glitter presets…</option>';Object.keys(p).sort().forEach(n=>{const o=document.createElement('option');o.value=n;o.textContent=n;presetList.appendChild(o);});}

  function touch(){lastActivity=performance.now();if(idleHidden){document.body.classList.remove('idle-clean');idleHidden=false;}}
  function checkIdle(t){if(!idleHidden&&t-lastActivity>5000){document.body.classList.add('idle-clean');idleHidden=true;}}

  function frame(t){
    const dt=clamp(t-last,1,40);last=t;checkIdle(t);
    if(running){
      updateBackground(t);fadeOverlay();emitters.forEach(a=>moveActor(a,t,dt));wells.forEach(a=>moveActor(a,t,dt));
      for(const e of emitters){const n=Math.max(1,Math.round(e.rate*settings.speed*2));for(let i=0;i<n;i++)if(chance(.45))spawn(e);}
      if(chance(settings.burst*dt/1000*.55))burst();
      for(let i=particles.length-1;i>=0;i--){
        const p=particles[i];p.age+=dt;p.px=p.x;p.py=p.y;
        const f=Math.sin(p.y*.009+t*.00031+p.hue*.01)+Math.cos(p.x*.007-t*.00021);
        let ax=Math.cos(f*Math.PI)*settings.noise*.012,ay=Math.sin(f*Math.PI)*settings.noise*.012;
        const dx0=width/2-p.x,dy0=height/2-p.y,d0=Math.hypot(dx0,dy0)+1;
        ax+=(-dy0/d0)*settings.swirl*.005;ay+=(dx0/d0)*settings.swirl*.005;
        ax+=Math.sin(t*.00017+p.angle)*settings.drift*.003;ay+=Math.cos(t*.00019+p.angle)*settings.drift*.003;
        for(const w of wells){
          const dx=w.x-p.x,dy=w.y-p.y,d=Math.hypot(dx,dy)+1;
          if(d<w.radius){const q=(1-d/w.radius)*(w.strength>0?settings.attraction:settings.repulsion)*Math.sign(w.strength)*.025;ax+=(dx/d)*q;ay+=(dy/d)*q;}
        }
        p.vx=(p.vx+ax)*.993;p.vy=(p.vy+ay)*.993;
        p.x+=p.vx*settings.speed*dt*.06;p.y+=p.vy*settings.speed*dt*.06;p.angle+=p.spin*dt*.04;
        if(p.age>p.life||p.x<-120||p.x>width+120||p.y<-120||p.y>height+120){particles.splice(i,1);continue;}
        drawParticle(p,t);
      }
      fpsFrames++;
    }
    if(t-fpsStamp>700){fpsEl.textContent=`${Math.round(fpsFrames*1000/(t-fpsStamp))} FPS`;fpsFrames=0;fpsStamp=t;}
    requestAnimationFrame(frame);
  }

  document.getElementById('randomize').onclick=()=>{randomize();touch();};
  document.getElementById('mutate').onclick=()=>{mutate();touch();};
  document.getElementById('pause').onclick=e=>{running=!running;e.currentTarget.textContent=running?'PAUSE':'RESUME';touch();};
  document.getElementById('fullscreen').onclick=()=>{document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen();touch();};
  document.getElementById('applySeed').onclick=()=>{seed=Number(seedInput.value)||0;rng=mulberry32(seed);particles=[];emitters=[];wells=[];reconcile();sync();touch();};
  document.getElementById('hidePanel').onclick=()=>{panel.classList.add('hidden');showPanel.classList.remove('hidden');touch();};
  showPanel.onclick=()=>{panel.classList.remove('hidden');showPanel.classList.add('hidden');touch();};
  document.getElementById('savePreset').onclick=()=>{const n=presetName.value.trim()||`Glitter ${new Date().toLocaleTimeString()}`;const p=presets();p[n]=state();localStorage.setItem('bloomsaver.glitter.presets',JSON.stringify(p));presetName.value='';refreshPresets();presetList.value=n;touch();};
  document.getElementById('loadPreset').onclick=()=>{const p=presets();if(p[presetList.value])loadState(p[presetList.value]);touch();};
  document.getElementById('deletePreset').onclick=()=>{const p=presets(),n=presetList.value;if(n&&p[n]){delete p[n];localStorage.setItem('bloomsaver.glitter.presets',JSON.stringify(p));refreshPresets();}touch();};
  ['pointermove','pointerdown','touchstart','wheel','keydown'].forEach(n=>addEventListener(n,touch,{passive:true}));
  addEventListener('resize',resize);
  addEventListener('keydown',e=>{if(['INPUT','SELECT','TEXTAREA'].includes(document.activeElement.tagName))return;const k=e.key.toLowerCase();if(k==='r')randomize();if(k==='m')mutate();if(k==='f')document.getElementById('fullscreen').click();if(k==='h')document.getElementById(panel.classList.contains('hidden')?'showPanel':'hidePanel').click();if(e.code==='Space'){e.preventDefault();document.getElementById('pause').click();}});

  resize();buildControls();refreshPresets();reconcile();sync();requestAnimationFrame(frame);
})();