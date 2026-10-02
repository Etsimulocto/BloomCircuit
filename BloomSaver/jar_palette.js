(() => {
  'use strict';

  const STORAGE_KEY='bloomsaver.matchJarOnStart';
  const PALETTE_KEYS=['happyjarz.activePalette','happyjarz.palette'];
  const originalCreateLinearGradient=CanvasRenderingContext2D.prototype.createLinearGradient;
  let matchOnStart=localStorage.getItem(STORAGE_KEY)==='1';
  let palette=null;
  let fadeStart=0;
  let fadeDuration=20000;

  function clamp(v,a,b){return Math.max(a,Math.min(b,v));}
  function hueDistance(a,b){let d=Math.abs(a-b)%360;return d>180?360-d:d;}
  function mixHue(a,b,t){let d=((b-a+540)%360)-180;return (a+d*t+360)%360;}

  function rgbToHue(r,g,b){
    r=clamp(Number(r)/255,0,1);g=clamp(Number(g)/255,0,1);b=clamp(Number(b)/255,0,1);
    const max=Math.max(r,g,b),min=Math.min(r,g,b),d=max-min;
    if(!d)return 0;
    let h=max===r?((g-b)/d)%6:max===g?(b-r)/d+2:(r-g)/d+4;
    return ((h*60)%360+360)%360;
  }

  function parseColor(value){
    if(value==null)return null;
    if(typeof value==='number'&&Number.isFinite(value))return ((value%360)+360)%360;
    if(typeof value==='object'){
      if(Number.isFinite(value.hue))return ((value.hue%360)+360)%360;
      if(Number.isFinite(value.h))return ((value.h%360)+360)%360;
      if(Number.isFinite(value.r)&&Number.isFinite(value.g)&&Number.isFinite(value.b))return rgbToHue(value.r,value.g,value.b);
    }
    const text=String(value).trim();
    const hsl=text.match(/hsla?\(\s*(-?[\d.]+)/i);if(hsl)return ((Number(hsl[1])%360)+360)%360;
    const hex=text.match(/^#?([0-9a-f]{6}|[0-9a-f]{3})$/i);
    if(hex){let h=hex[1];if(h.length===3)h=h.split('').map(x=>x+x).join('');return rgbToHue(parseInt(h.slice(0,2),16),parseInt(h.slice(2,4),16),parseInt(h.slice(4,6),16));}
    const rgb=text.match(/rgba?\(\s*([\d.]+)\s*[, ]\s*([\d.]+)\s*[, ]\s*([\d.]+)/i);
    if(rgb)return rgbToHue(Number(rgb[1]),Number(rgb[2]),Number(rgb[3]));
    const n=Number(text);return Number.isFinite(n)?((n%360)+360)%360:null;
  }

  function normalizePalette(input){
    if(!input)return null;
    let raw=input;
    if(typeof raw==='string'){
      try{raw=JSON.parse(raw);}catch{raw=raw.split(/[;,|]/).map(v=>v.trim()).filter(Boolean);}
    }
    let colors=[];
    if(Array.isArray(raw))colors=raw;
    else if(raw.colors&&Array.isArray(raw.colors))colors=raw.colors;
    else colors=[raw.primary,raw.secondary,raw.accent,raw.color1,raw.color2,raw.color3].filter(v=>v!=null);
    const hues=colors.map(parseColor).filter(Number.isFinite).slice(0,6);
    if(!hues.length)return null;
    return {hues,source:raw.name||raw.id||raw.pattern||'HAPPY JARZ'};
  }

  function discoverPalette(){
    for(const candidate of [window.HAPPY_JARZ_PALETTE,window.HappyJarzPalette,window.jarPalette]){
      const p=normalizePalette(candidate);if(p)return p;
    }
    for(const key of PALETTE_KEYS){
      try{const p=normalizePalette(localStorage.getItem(key));if(p)return p;}catch{}
    }
    const q=new URLSearchParams(location.search);
    return normalizePalette([q.get('jarPrimary'),q.get('jarSecondary'),q.get('jarAccent')].filter(Boolean));
  }

  function setSlider(key,value){
    const el=document.querySelector(`[data-key="${key}"]`);
    if(!el)return;
    el.value=value;
    el.dispatchEvent(new Event('input',{bubbles:true}));
  }

  function applyPalette(p){
    palette=normalizePalette(p)||p;
    if(!palette||!palette.hues?.length)return false;
    const hues=palette.hues;
    setSlider('hue',hues[0]);
    if(hues.length>1){
      const ds=[];
      for(let i=0;i<hues.length;i++)for(let j=i+1;j<hues.length;j++)ds.push(hueDistance(hues[i],hues[j]));
      setSlider('hueSpread',clamp(Math.max(18,...ds),0,180));
    }
    fadeStart=performance.now();
    updateButton();
    return true;
  }

  function updateButton(){
    const b=document.getElementById('matchJarStart');if(!b)return;
    b.textContent=`MATCH JAR COLORS ON START: ${matchOnStart?'ON':'OFF'}`;
    b.classList.toggle('active',matchOnStart);
    b.title=palette?`Startup palette: ${palette.source}. User edits are free after startup.`:'When embedded in HAPPY JARZ, start from the active light-pattern colors; user edits remain free afterward.';
  }

  function installButton(){
    if(document.getElementById('matchJarStart'))return;
    const grid=document.querySelector('.primary-actions');if(!grid)return;
    const b=document.createElement('button');
    b.id='matchJarStart';b.style.gridColumn='1 / -1';
    grid.appendChild(b);
    b.addEventListener('click',()=>{
      matchOnStart=!matchOnStart;
      localStorage.setItem(STORAGE_KEY,matchOnStart?'1':'0');
      if(matchOnStart){palette=palette||discoverPalette();if(palette)applyPalette(palette);}
      updateButton();
    });
    updateButton();
  }

  CanvasRenderingContext2D.prototype.createLinearGradient=function(...args){
    const gradient=originalCreateLinearGradient.apply(this,args);
    const originalAdd=gradient.addColorStop.bind(gradient);
    gradient.addColorStop=(offset,color)=>{
      if(matchOnStart&&palette?.hues?.length&&fadeStart){
        const age=performance.now()-fadeStart;
        if(age<fadeDuration){
          const m=clamp(age/fadeDuration,0,1);
          const originalHue=parseColor(color);
          const base=palette.hues[offset>=.5?1%palette.hues.length:0];
          const hue=Number.isFinite(originalHue)?mixHue(base,originalHue,m):base;
          const sat=document.querySelector('[data-key="bgSaturation"]')?.value||46;
          const bright=document.querySelector('[data-key="bgBrightness"]')?.value||11;
          const light=offset>=.5?Math.max(1,Number(bright)-3):Number(bright);
          color=`hsl(${hue} ${sat}% ${light}%)`;
        }
      }
      return originalAdd(offset,color);
    };
    return gradient;
  };

  window.BloomSaver=window.BloomSaver||{};
  window.BloomSaver.setJarPalette=(incoming,options={})=>{
    palette=normalizePalette(incoming);
    if(!palette)return false;
    if(options.applyNow||(matchOnStart&&!fadeStart))applyPalette(palette);
    updateButton();
    return true;
  };

  addEventListener('message',event=>{
    const data=event.data;
    if(data&&(data.type==='happyjarz-palette'||data.type==='HAPPY_JARZ_PALETTE')){
      window.BloomSaver.setJarPalette(data.palette||data.colors||data,{applyNow:false});
    }
  });

  installButton();
  palette=discoverPalette();
  if(matchOnStart&&palette)applyPalette(palette);
  updateButton();
})();
