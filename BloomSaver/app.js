(() => {
  "use strict";

  const canvas = document.getElementById("stage");
  const ctx = canvas.getContext("2d", { alpha: false });
  const panel = document.getElementById("panel");
  const controlsEl = document.getElementById("controls");
  const fpsEl = document.getElementById("fps");
  const seedLabel = document.getElementById("seedLabel");
  const seedInput = document.getElementById("seed");
  const modeSelect = document.getElementById("mode");
  const autoEvolve = document.getElementById("autoEvolve");
  const evolveSeconds = document.getElementById("evolveSeconds");
  const mutation = document.getElementById("mutation");
  const presetList = document.getElementById("presetList");
  const presetName = document.getElementById("presetName");

  const schema = {
    count:      { label:"Particles", min:20, max:700, step:1, value:220 },
    speed:      { label:"Speed", min:.05, max:3, step:.01, value:.8 },
    trails:     { label:"Trails", min:0, max:.98, step:.01, value:.9 },
    links:      { label:"Link distance", min:0, max:220, step:1, value:90 },
    attraction: { label:"Attraction", min:-2, max:2, step:.01, value:.42 },
    repel:      { label:"Repel", min:0, max:3, step:.01, value:.55 },
    noise:      { label:"Field noise", min:0, max:3, step:.01, value:.75 },
    swirl:      { label:"Swirl", min:-3, max:3, step:.01, value:.8 },
    glow:       { label:"Glow", min:0, max:40, step:1, value:18 },
    symmetry:   { label:"Symmetry", min:1, max:12, step:1, value:3 },
    hue:        { label:"Hue", min:0, max:360, step:1, value:190 },
    hueSpread:  { label:"Hue spread", min:0, max:180, step:1, value:70 },
    pulse:      { label:"Pulse", min:0, max:3, step:.01, value:.55 },
    scale:      { label:"Scale", min:.2, max:3, step:.01, value:1.1 }
  };

  let settings = Object.fromEntries(Object.entries(schema).map(([k,v]) => [k,v.value]));
  let seed = Math.floor(Math.random() * 1e9);
  let rng = mulberry32(seed);
  let particles = [];
  let running = true;
  let frame = 0;
  let last = performance.now();
  let fpsStamp = last;
  let fpsFrames = 0;
  let evolveStamp = last;
  let width = innerWidth, height = innerHeight, dpr = Math.min(devicePixelRatio || 1, 2);

  function mulberry32(a) {
    return function() {
      let t = a += 0x6D2B79F5;
      t = Math.imul(t ^ t >>> 15, t | 1);
      t ^= t + Math.imul(t ^ t >>> 7, t | 61);
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }

  function rand(a=0,b=1){ return a + (b-a) * rng(); }
  function clamp(v,a,b){ return Math.max(a,Math.min(b,v)); }

  function resize(){
    width = innerWidth; height = innerHeight; dpr = Math.min(devicePixelRatio || 1, 2);
    canvas.width = Math.floor(width*dpr); canvas.height = Math.floor(height*dpr);
    canvas.style.width = width+"px"; canvas.style.height = height+"px";
    ctx.setTransform(dpr,0,0,dpr,0,0);
    ctx.fillStyle = "#03040a"; ctx.fillRect(0,0,width,height);
  }

  function makeParticle(i){
    const a = rand(0,Math.PI*2), r = rand(20,Math.min(width,height)*.45);
    return {
      x: width/2 + Math.cos(a)*r,
      y: height/2 + Math.sin(a)*r,
      px: width/2, py: height/2,
      vx: rand(-1,1), vy: rand(-1,1),
      life: rand(0,1000), size: rand(.6,2.8), phase: rand(0,Math.PI*2), lane:i
    };
  }

  function rebuild(){
    rng = mulberry32(seed);
    particles = Array.from({length:Math.floor(settings.count)},(_,i)=>makeParticle(i));
    seedInput.value = seed;
    seedLabel.textContent = `SEED ${seed}`;
    ctx.fillStyle = "#03040a"; ctx.fillRect(0,0,width,height);
  }

  function setSetting(key,value){
    settings[key] = Number(value);
    const out = document.querySelector(`[data-out="${key}"]`);
    if(out) out.value = format(settings[key]);
    if(key === "count") rebuild();
  }

  function format(v){ return Math.abs(v-Math.round(v)) < .0001 ? String(Math.round(v)) : v.toFixed(2); }

  function buildControls(){
    controlsEl.innerHTML = "";
    for(const [key,s] of Object.entries(schema)){
      const wrap = document.createElement("div"); wrap.className = "control";
      wrap.innerHTML = `<div class="control-head"><span>${s.label}</span><output data-out="${key}">${format(settings[key])}</output></div><input data-key="${key}" type="range" min="${s.min}" max="${s.max}" step="${s.step}" value="${settings[key]}">`;
      wrap.querySelector("input").addEventListener("input", e => setSetting(key,e.target.value));
      controlsEl.appendChild(wrap);
    }
  }

  function color(i,alpha=1,offset=0){
    const hue = (settings.hue + offset + ((i%29)/29-.5)*settings.hueSpread + 360)%360;
    return `hsla(${hue},92%,68%,${alpha})`;
  }

  function fadeBackground(){
    const a = 1 - settings.trails;
    ctx.fillStyle = `rgba(3,4,10,${Math.max(.015,a)})`;
    ctx.fillRect(0,0,width,height);
  }

  function drawUniverse(t,dt){
    const cx = width/2 + Math.cos(t*.00013)*width*.08;
    const cy = height/2 + Math.sin(t*.00017)*height*.08;
    fadeBackground();
    ctx.lineWidth = .7;
    for(let i=0;i<particles.length;i++){
      const p=particles[i]; p.px=p.x; p.py=p.y;
      const dx=cx-p.x,dy=cy-p.y,dist=Math.hypot(dx,dy)+.001;
      const n=Math.sin(p.x*.008*settings.scale + t*.0004 + p.phase) + Math.cos(p.y*.009*settings.scale - t*.0003);
      p.vx += (dx/dist)*settings.attraction*.012 + (-dy/dist)*settings.swirl*.01 + Math.cos(n*3+p.phase)*settings.noise*.009;
      p.vy += (dy/dist)*settings.attraction*.012 + ( dx/dist)*settings.swirl*.01 + Math.sin(n*3+p.phase)*settings.noise*.009;
      if(dist < 110){ const f=(110-dist)/110*settings.repel*.035; p.vx -= dx/dist*f; p.vy -= dy/dist*f; }
      p.vx*=.993; p.vy*=.993; p.x+=p.vx*settings.speed*dt*.06; p.y+=p.vy*settings.speed*dt*.06;
      wrap(p);
      ctx.strokeStyle=color(i,.42); ctx.shadowBlur=settings.glow; ctx.shadowColor=color(i,.45);
      ctx.beginPath();ctx.moveTo(p.px,p.py);ctx.lineTo(p.x,p.y);ctx.stroke();
    }
    drawLinks();
  }

  function drawSilk(t,dt){
    fadeBackground();
    ctx.lineWidth=1;
    const sym=Math.max(1,Math.round(settings.symmetry));
    for(let i=0;i<particles.length;i++){
      const p=particles[i];p.px=p.x;p.py=p.y;
      const a=Math.sin(p.y*.008*settings.scale+t*.00035+p.phase)*settings.noise + Math.cos(p.x*.006-t*.00022);
      p.vx += Math.cos(a*Math.PI)*.015*settings.swirl;
      p.vy += Math.sin(a*Math.PI)*.015*settings.swirl;
      p.vx*=.985;p.vy*=.985;p.x+=p.vx*settings.speed*dt*.07;p.y+=p.vy*settings.speed*dt*.07;wrap(p);
      for(let s=0;s<sym;s++){
        const ang=(Math.PI*2/sym)*s;
        const x=width/2+(p.x-width/2)*Math.cos(ang)-(p.y-height/2)*Math.sin(ang);
        const y=height/2+(p.x-width/2)*Math.sin(ang)+(p.y-height/2)*Math.cos(ang);
        ctx.fillStyle=color(i,.13+s*.015,s*6);ctx.shadowBlur=settings.glow;ctx.shadowColor=color(i,.4);
        ctx.beginPath();ctx.arc(x,y,p.size*settings.scale,0,Math.PI*2);ctx.fill();
      }
    }
  }

  function drawCrystal(t){
    fadeBackground();
    const cx=width/2,cy=height/2,sym=Math.max(2,Math.round(settings.symmetry));
    ctx.save();ctx.translate(cx,cy);ctx.rotate(t*.00002*settings.speed);
    for(let ring=0;ring<Math.min(80,Math.floor(settings.count/4));ring++){
      const r=(ring+1)*5*settings.scale;
      const wobble=Math.sin(t*.0007+ring*.8)*14*settings.pulse;
      for(let s=0;s<sym;s++){
        const a=s/sym*Math.PI*2 + Math.sin(ring*.23+t*.00009)*.18*settings.noise;
        const x=Math.cos(a)*(r+wobble),y=Math.sin(a)*(r+wobble);
        const len=8+Math.sin(ring*.7+t*.001)*6;
        ctx.strokeStyle=color(ring,.26,s*9);ctx.lineWidth=.7+settings.scale*.35;ctx.shadowBlur=settings.glow;ctx.shadowColor=color(ring,.35);
        ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x+Math.cos(a+.7)*len,y+Math.sin(a+.7)*len);ctx.stroke();
      }
    }
    ctx.restore();
  }

  function drawOrbit(t,dt){
    fadeBackground();
    const cx=width/2,cy=height/2;
    for(let i=0;i<particles.length;i++){
      const p=particles[i];p.life+=dt*.001*settings.speed;
      const base=28+(i%90)*4.2*settings.scale;
      const eccentric=.55+.35*Math.sin(i*1.73);
      const a=p.life*(.14+((i%13)/13)*.5) + p.phase;
      const pulse=1+Math.sin(t*.001*settings.pulse+p.phase)*.05;
      p.x=cx+Math.cos(a)*base*pulse;p.y=cy+Math.sin(a)*base*eccentric*pulse;
      ctx.fillStyle=color(i,.5);ctx.shadowBlur=settings.glow;ctx.shadowColor=color(i,.6);
      ctx.beginPath();ctx.arc(p.x,p.y,Math.max(.7,p.size*settings.scale),0,Math.PI*2);ctx.fill();
      if(i%17===0){ctx.strokeStyle=color(i,.08);ctx.beginPath();ctx.ellipse(cx,cy,base,base*eccentric,0,0,Math.PI*2);ctx.stroke();}
    }
  }

  function drawRain(t,dt){
    fadeBackground();
    const columns=Math.max(12,Math.floor(settings.count/5));
    const w=width/columns;
    ctx.font=`${10+settings.scale*5}px ui-monospace,monospace`;
    for(let i=0;i<particles.length;i++){
      const p=particles[i];
      p.y += (18+(i%11)*4)*settings.speed*dt*.06;
      p.x = (i%columns)*w + w*.5 + Math.sin(t*.0007+p.phase)*w*.25*settings.noise;
      if(p.y>height+30){p.y=-rand(10,height*.8);p.phase=rand(0,Math.PI*2);}
      const glyph=String.fromCharCode(0x2500 + ((i*17+Math.floor(t/180))%128));
      ctx.fillStyle=color(i,.15+((i%7)/7)*.45);ctx.shadowBlur=settings.glow*.5;ctx.shadowColor=color(i,.45);
      ctx.fillText(glyph,p.x,p.y);
    }
  }

  function drawLinks(){
    const d=settings.links;if(d<=0||particles.length>420)return;
    ctx.shadowBlur=0;
    for(let i=0;i<particles.length;i++)for(let j=i+1;j<particles.length;j++){
      const a=particles[i],b=particles[j],dx=a.x-b.x,dy=a.y-b.y,dd=dx*dx+dy*dy;
      if(dd<d*d){const alpha=(1-Math.sqrt(dd)/d)*.12;ctx.strokeStyle=color(i,alpha);ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();}
    }
  }

  function wrap(p){
    const m=40;if(p.x<-m){p.x=width+m;p.px=p.x}if(p.x>width+m){p.x=-m;p.px=p.x}if(p.y<-m){p.y=height+m;p.py=p.y}if(p.y>height+m){p.y=-m;p.py=p.y}
  }

  function render(t){
    const dt=clamp(t-last,1,40); last=t;
    if(running){
      frame++; fpsFrames++;
      const mode=modeSelect.value;
      if(mode==="silk") drawSilk(t,dt); else if(mode==="crystal") drawCrystal(t); else if(mode==="orbit") drawOrbit(t,dt); else if(mode==="rain") drawRain(t,dt); else drawUniverse(t,dt);
      if(autoEvolve.checked && t-evolveStamp > Number(evolveSeconds.value)*1000){ mutateSettings(Number(mutation.value)/100); evolveStamp=t; }
    }
    if(t-fpsStamp>700){fpsEl.textContent=`${Math.round(fpsFrames*1000/(t-fpsStamp))} FPS`;fpsFrames=0;fpsStamp=t;}
    requestAnimationFrame(render);
  }

  function randomSettings(){
    seed=Math.floor(Math.random()*1e9);rng=mulberry32(seed);
    modeSelect.value=["universe","silk","crystal","orbit","rain"][Math.floor(rand(0,5))];
    for(const [k,s] of Object.entries(schema)){
      let v=rand(s.min,s.max); if(s.step>=1)v=Math.round(v); else v=Math.round(v/s.step)*s.step;
      settings[k]=clamp(v,s.min,s.max);
    }
    settings.count=Math.round(rand(90,380));settings.trails=rand(.78,.96);settings.glow=rand(7,30);settings.links=rand(20,145);
    syncControls();rebuild();
  }

  function mutateSettings(strength=.24){
    rng=mulberry32((seed + frame*7919)>>>0);
    for(const [k,s] of Object.entries(schema)){
      if(k==="count" && rng()>.28) continue;
      const span=s.max-s.min; settings[k]=clamp(settings[k]+(rng()-.5)*span*strength,s.min,s.max);
      if(s.step>=1)settings[k]=Math.round(settings[k]); else settings[k]=Math.round(settings[k]/s.step)*s.step;
    }
    if(rng()<strength*.45){ const modes=["universe","silk","crystal","orbit","rain"]; modeSelect.value=modes[Math.floor(rng()*modes.length)]; }
    seed=(seed+Math.floor(rng()*1000003))>>>0;syncControls();rebuild();
  }

  function syncControls(){
    document.querySelectorAll("[data-key]").forEach(el=>{el.value=settings[el.dataset.key];});
    document.querySelectorAll("[data-out]").forEach(el=>{el.value=format(settings[el.dataset.out]);});
    seedInput.value=seed;seedLabel.textContent=`SEED ${seed}`;
  }

  function state(){return {version:1,seed,mode:modeSelect.value,settings:{...settings},autoEvolve:autoEvolve.checked,evolveSeconds:Number(evolveSeconds.value),mutation:Number(mutation.value)};}
  function loadState(s){if(!s)return;seed=Number(s.seed)||seed;modeSelect.value=s.mode||"universe";settings={...settings,...s.settings};autoEvolve.checked=s.autoEvolve!==false;evolveSeconds.value=s.evolveSeconds||18;mutation.value=s.mutation||24;syncControls();rebuild();}

  function presets(){try{return JSON.parse(localStorage.getItem("bloomsaver.presets")||"{}")}catch{return {}}}
  function refreshPresets(){const p=presets();presetList.innerHTML='<option value="">Saved presets…</option>';Object.keys(p).sort().forEach(name=>{const o=document.createElement("option");o.value=name;o.textContent=name;presetList.appendChild(o);});}

  document.getElementById("randomize").onclick=randomSettings;
  document.getElementById("mutate").onclick=()=>mutateSettings(Number(mutation.value)/100);
  document.getElementById("pause").onclick=e=>{running=!running;e.currentTarget.textContent=running?"PAUSE":"RESUME";};
  document.getElementById("fullscreen").onclick=()=>document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen();
  document.getElementById("applySeed").onclick=()=>{seed=Number(seedInput.value)||0;rebuild();};
  document.getElementById("hidePanel").onclick=()=>{panel.classList.add("hidden");document.getElementById("showPanel").classList.remove("hidden");};
  document.getElementById("showPanel").onclick=()=>{panel.classList.remove("hidden");document.getElementById("showPanel").classList.add("hidden");};
  document.getElementById("savePreset").onclick=()=>{const name=presetName.value.trim()||`Bloom ${new Date().toLocaleTimeString()}`;const p=presets();p[name]=state();localStorage.setItem("bloomsaver.presets",JSON.stringify(p));presetName.value="";refreshPresets();presetList.value=name;};
  document.getElementById("loadPreset").onclick=()=>{const p=presets();if(p[presetList.value])loadState(p[presetList.value]);};
  document.getElementById("deletePreset").onclick=()=>{const p=presets(),name=presetList.value;if(name&&p[name]){delete p[name];localStorage.setItem("bloomsaver.presets",JSON.stringify(p));refreshPresets();}};
  modeSelect.onchange=()=>rebuild();
  addEventListener("resize",resize);
  addEventListener("keydown",e=>{
    if(["INPUT","SELECT","TEXTAREA"].includes(document.activeElement.tagName))return;
    const k=e.key.toLowerCase();if(k==="r")randomSettings();if(k==="m")mutateSettings(Number(mutation.value)/100);if(k==="f")document.getElementById("fullscreen").click();if(k==="h")document.getElementById(panel.classList.contains("hidden")?"showPanel":"hidePanel").click();if(e.code==="Space"){e.preventDefault();document.getElementById("pause").click();}
  });

  resize();buildControls();refreshPresets();rebuild();requestAnimationFrame(render);
})();
