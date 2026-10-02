(() => {
  "use strict";

  const baseCanvas = document.getElementById("stage");
  const mode = document.getElementById("mode");
  const panel = document.getElementById("panel");
  const showPanel = document.getElementById("showPanel");
  const primary = document.querySelector(".primary-actions");

  // Add Glitter Jar as a first-class selectable BloomSaver mode.
  if (mode && !mode.querySelector('option[value="glitter"]')) {
    const option = document.createElement("option");
    option.value = "glitter";
    option.textContent = "Glitter Jar";
    mode.appendChild(option);
  }

  const glitterButton = document.createElement("button");
  glitterButton.id = "glitterPreset";
  glitterButton.textContent = "GLITTER JAR";
  glitterButton.title = "Load the built-in floating glitter preset";
  if (primary) primary.appendChild(glitterButton);

  const canvas = document.createElement("canvas");
  canvas.id = "glitterStage";
  canvas.setAttribute("aria-hidden", "true");
  document.body.insertBefore(canvas, document.querySelector(".topbar"));
  const ctx = canvas.getContext("2d", { alpha: false });

  let width = innerWidth;
  let height = innerHeight;
  let dpr = Math.min(devicePixelRatio || 1, 2);
  let flakes = [];
  let last = performance.now();
  let active = false;
  let idleTimer = 0;

  function num(key, fallback) {
    const el = document.querySelector(`[data-key="${key}"]`);
    const value = el ? Number(el.value) : fallback;
    return Number.isFinite(value) ? value : fallback;
  }

  function setControl(key, value) {
    const el = document.querySelector(`[data-key="${key}"]`);
    if (!el) return;
    el.value = value;
    el.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function resize() {
    width = innerWidth;
    height = innerHeight;
    dpr = Math.min(devicePixelRatio || 1, 2);
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    buildFlakes(true);
  }

  function desiredCount() {
    return Math.max(30, Math.min(700, Math.floor(num("count", 360))));
  }

  function makeFlake(i) {
    return {
      x: Math.random(),
      y: Math.random(),
      vx: (Math.random() - .5) * .018,
      vy: .012 + Math.random() * .055,
      size: .65 + Math.random() * 2.8,
      phase: Math.random() * Math.PI * 2,
      spin: (Math.random() - .5) * .08,
      angle: Math.random() * Math.PI,
      hueOffset: (Math.random() - .5) * 2,
      twinkle: .45 + Math.random() * 1.8,
      lane: i
    };
  }

  function buildFlakes(force = false) {
    const count = desiredCount();
    if (!force && flakes.length === count) return;
    if (flakes.length < count) {
      for (let i = flakes.length; i < count; i += 1) flakes.push(makeFlake(i));
    } else {
      flakes.length = count;
    }
  }

  function jarBox() {
    const portrait = height > width;
    const w = Math.min(width * (portrait ? .78 : .58), 760);
    const h = Math.min(height * .82, 850);
    return { x:(width-w)/2, y:(height-h)/2 + 8, w, h };
  }

  function jarPath(box) {
    const {x,y,w,h} = box;
    const neck = w * .18;
    const shoulderY = y + h * .105;
    const bottomR = Math.min(46, w * .075);
    ctx.beginPath();
    ctx.moveTo(x + w*.5 - neck, y);
    ctx.lineTo(x + w*.5 + neck, y);
    ctx.lineTo(x + w*.5 + neck, y + h*.04);
    ctx.bezierCurveTo(x+w*.82, y+h*.065, x+w*.93, shoulderY, x+w*.93, y+h*.20);
    ctx.lineTo(x+w*.93, y+h-bottomR);
    ctx.quadraticCurveTo(x+w*.93, y+h, x+w*.93-bottomR, y+h);
    ctx.lineTo(x+w*.07+bottomR, y+h);
    ctx.quadraticCurveTo(x+w*.07, y+h, x+w*.07, y+h-bottomR);
    ctx.lineTo(x+w*.07, y+h*.20);
    ctx.bezierCurveTo(x+w*.07, shoulderY, x+w*.18, y+h*.065, x+w*.5-neck, y+h*.04);
    ctx.closePath();
  }

  function colorFor(flake, alpha) {
    const hue = num("hue", 42);
    const spread = num("hueSpread", 145);
    const h = (hue + flake.hueOffset * spread + 360) % 360;
    return `hsla(${h},96%,72%,${alpha})`;
  }

  function drawBackground(t) {
    const hue = num("hue", 42);
    const grad = ctx.createRadialGradient(width*.5,height*.42,10,width*.5,height*.5,Math.max(width,height)*.72);
    grad.addColorStop(0, `hsla(${(hue+30)%360},45%,10%,1)`);
    grad.addColorStop(.48, "#070812");
    grad.addColorStop(1, "#020306");
    ctx.fillStyle = grad;
    ctx.fillRect(0,0,width,height);

    const pulse = num("pulse", .35);
    const glow = .04 + (Math.sin(t*.00045)+1)*.018*pulse;
    ctx.fillStyle = `rgba(255,255,255,${glow})`;
    ctx.beginPath();
    ctx.ellipse(width*.5,height*.47,width*.22,height*.38,0,0,Math.PI*2);
    ctx.fill();
  }

  function drawGlitter(t, dt) {
    buildFlakes();
    drawBackground(t);
    const box = jarBox();
    const speed = num("speed", .42);
    const noise = num("noise", .62);
    const swirl = num("swirl", .18);
    const scale = num("scale", 1.25);
    const glow = num("glow", 20);

    ctx.save();
    jarPath(box);
    ctx.clip();

    // faint liquid/glass body
    const liquid = ctx.createLinearGradient(0,box.y,0,box.y+box.h);
    liquid.addColorStop(0,"rgba(255,255,255,.035)");
    liquid.addColorStop(.55,"rgba(100,130,200,.025)");
    liquid.addColorStop(1,"rgba(255,255,255,.06)");
    ctx.fillStyle = liquid;
    ctx.fillRect(box.x,box.y,box.w,box.h);

    for (const f of flakes) {
      const wave = Math.sin(t*.00048 + f.phase + f.y*7) * noise;
      const eddy = Math.cos(t*.00019 + f.phase*1.7 + f.x*9) * swirl;
      f.vx += (wave*.000085 + eddy*.000055) * dt;
      f.vx *= .985;
      f.x += f.vx * speed * dt * .06;
      f.y += f.vy * speed * dt * .06;
      f.angle += f.spin * speed * dt * .04;

      // slow suspended settling with recirculation from the bottom.
      if (f.y > .965) {
        f.y = .08 + Math.random()*.08;
        f.x = .14 + Math.random()*.72;
        f.vx = (Math.random()-.5)*.02;
      }
      if (f.x < .08) { f.x=.08; f.vx=Math.abs(f.vx); }
      if (f.x > .92) { f.x=.92; f.vx=-Math.abs(f.vx); }

      const x = box.x + f.x*box.w;
      const y = box.y + f.y*box.h;
      const shimmer = .36 + .64*Math.abs(Math.sin(t*.0012*f.twinkle + f.phase));
      const s = f.size * scale * (1 + shimmer*.32);

      ctx.save();
      ctx.translate(x,y);
      ctx.rotate(f.angle);
      ctx.shadowBlur = glow * (.35 + shimmer*.8);
      ctx.shadowColor = colorFor(f,.85);
      ctx.fillStyle = colorFor(f,.35 + shimmer*.64);
      if (f.lane % 3 === 0) {
        ctx.beginPath();
        ctx.moveTo(0,-s*1.5); ctx.lineTo(s*.72,0); ctx.lineTo(0,s*1.5); ctx.lineTo(-s*.72,0); ctx.closePath();
        ctx.fill();
      } else if (f.lane % 3 === 1) {
        ctx.fillRect(-s*.65,-s*.18,s*1.3,s*.36);
        ctx.fillRect(-s*.18,-s*.65,s*.36,s*1.3);
      } else {
        ctx.beginPath(); ctx.arc(0,0,s*.58,0,Math.PI*2); ctx.fill();
      }
      ctx.restore();
    }
    ctx.restore();

    // Glass outline and mouth stay subtle so it still reads as a screensaver.
    ctx.save();
    ctx.lineWidth = 1.2;
    ctx.strokeStyle = "rgba(205,225,255,.18)";
    ctx.shadowBlur = 14;
    ctx.shadowColor = "rgba(140,190,255,.12)";
    jarPath(box);
    ctx.stroke();
    ctx.strokeStyle = "rgba(255,255,255,.12)";
    ctx.beginPath();
    ctx.moveTo(box.x+box.w*.32,box.y+box.h*.18);
    ctx.bezierCurveTo(box.x+box.w*.20,box.y+box.h*.36,box.x+box.w*.23,box.y+box.h*.65,box.x+box.w*.29,box.y+box.h*.82);
    ctx.stroke();
    ctx.restore();
  }

  function setActive(next) {
    active = next;
    canvas.classList.toggle("active", active);
    baseCanvas.classList.toggle("glitter-hidden", active);
    if (active) buildFlakes(true);
  }

  function applyGlitterPreset() {
    mode.value = "glitter";
    const values = {
      count: 420, speed:.42, trails:.86, links:0, attraction:0, repel:.08,
      noise:.62, swirl:.18, glow:20, symmetry:1, hue:42, hueSpread:145,
      pulse:.35, scale:1.25
    };
    Object.entries(values).forEach(([key,value]) => setControl(key,value));
    setActive(true);
    revealUI();
  }

  glitterButton.addEventListener("click", applyGlitterPreset);
  mode.addEventListener("change", () => setActive(mode.value === "glitter"));

  // Buttons that deliberately choose another universe should drop the overlay.
  ["randomize","mutate"].forEach(id => {
    const button = document.getElementById(id);
    if (button) button.addEventListener("click", () => setTimeout(() => setActive(mode.value === "glitter"), 0));
  });
  const loadPreset = document.getElementById("loadPreset");
  if (loadPreset) loadPreset.addEventListener("click", () => setTimeout(() => setActive(mode.value === "glitter"), 0));

  function hideUI() {
    document.body.classList.add("idle-clean");
  }

  function revealUI() {
    document.body.classList.remove("idle-clean");
    clearTimeout(idleTimer);
    idleTimer = setTimeout(hideUI, 5000);
  }

  ["pointermove","pointerdown","touchstart","wheel","keydown"].forEach(name => {
    addEventListener(name, revealUI, { passive:true });
  });
  if (panel) panel.addEventListener("input", revealUI);
  if (showPanel) showPanel.addEventListener("click", revealUI);

  function frame(t) {
    const dt = Math.min(40, Math.max(1, t-last));
    last = t;
    if (active) drawGlitter(t,dt);
    requestAnimationFrame(frame);
  }

  addEventListener("resize", resize);
  resize();
  revealUI();
  setActive(mode.value === "glitter");
  requestAnimationFrame(frame);
})();
