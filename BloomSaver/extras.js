(() => {
  "use strict";

  const mode = document.getElementById("mode");
  const panel = document.getElementById("panel");
  const showPanel = document.getElementById("showPanel");
  const primary = document.querySelector(".primary-actions");

  // Glitter is now an independent fullscreen overlay layer.
  // It does NOT replace or hide the selected BloomSaver base mode.
  const glitterButton = document.getElementById("glitterPreset") || document.createElement("button");
  glitterButton.id = "glitterPreset";
  glitterButton.textContent = "GLITTER OVERLAY";
  glitterButton.title = "Toggle fullscreen glitter over the current BloomSaver mode";
  if (!glitterButton.parentElement && primary) primary.appendChild(glitterButton);

  // Remove the old first-class Glitter Jar mode if it was injected by an earlier build.
  if (mode) {
    const oldGlitterOption = mode.querySelector('option[value="glitter"]');
    if (oldGlitterOption) oldGlitterOption.remove();
  }

  const canvas = document.createElement("canvas");
  canvas.id = "glitterStage";
  canvas.setAttribute("aria-hidden", "true");
  document.body.insertBefore(canvas, document.querySelector(".topbar"));
  const ctx = canvas.getContext("2d", { alpha: true });

  let width = innerWidth;
  let height = innerHeight;
  let dpr = Math.min(devicePixelRatio || 1, 2);
  let flakes = [];
  let last = performance.now();
  let active = true;
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
    return Math.max(40, Math.min(950, Math.floor(num("count", 420) * 1.25)));
  }

  function makeFlake(i) {
    return {
      x: Math.random(),
      y: Math.random(),
      vx: (Math.random() - .5) * .018,
      vy: .008 + Math.random() * .042,
      size: .7 + Math.random() * 3.2,
      phase: Math.random() * Math.PI * 2,
      spin: (Math.random() - .5) * .09,
      angle: Math.random() * Math.PI,
      hueOffset: (Math.random() - .5) * 2,
      twinkle: .45 + Math.random() * 1.8,
      depth: .45 + Math.random() * .9,
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

  function colorFor(flake, alpha) {
    const hue = num("hue", 42);
    const spread = num("hueSpread", 145);
    const h = (hue + flake.hueOffset * spread + 360) % 360;
    return `hsla(${h},96%,72%,${alpha})`;
  }

  function drawGlitter(t, dt) {
    buildFlakes();
    ctx.clearRect(0, 0, width, height);

    const speed = num("speed", .42);
    const noise = num("noise", .62);
    const swirl = num("swirl", .18);
    const scale = num("scale", 1.25);
    const glow = num("glow", 20);

    for (const f of flakes) {
      const wave = Math.sin(t * .00048 + f.phase + f.y * 7) * noise;
      const eddy = Math.cos(t * .00019 + f.phase * 1.7 + f.x * 9) * swirl;

      f.vx += (wave * .000075 + eddy * .00005) * dt;
      f.vx *= .985;
      f.x += f.vx * speed * dt * .06 * f.depth;
      f.y += f.vy * speed * dt * .06 * f.depth;
      f.angle += f.spin * speed * dt * .04;

      // Fullscreen recirculation: flakes drift off one edge and quietly return.
      if (f.y > 1.03) {
        f.y = -.03;
        f.x = Math.random();
        f.vx = (Math.random() - .5) * .02;
      }
      if (f.x < -.03) f.x = 1.03;
      if (f.x > 1.03) f.x = -.03;

      const x = f.x * width;
      const y = f.y * height;
      const shimmer = .28 + .72 * Math.abs(Math.sin(t * .0012 * f.twinkle + f.phase));
      const s = f.size * scale * (.82 + shimmer * .42) * f.depth;
      const c = colorFor(f, .28 + shimmer * .65);

      ctx.save();
      ctx.translate(x, y);
      ctx.rotate(f.angle);
      ctx.shadowBlur = glow * (.28 + shimmer * .7);
      ctx.shadowColor = c;
      ctx.fillStyle = c;
      ctx.strokeStyle = c;

      if (f.lane % 3 === 0) {
        ctx.beginPath();
        ctx.moveTo(0, -s * 1.5);
        ctx.lineTo(s * .72, 0);
        ctx.lineTo(0, s * 1.5);
        ctx.lineTo(-s * .72, 0);
        ctx.closePath();
        ctx.fill();
      } else if (f.lane % 3 === 1) {
        ctx.lineWidth = Math.max(.55, s * .22);
        ctx.beginPath();
        ctx.moveTo(-s, 0);
        ctx.lineTo(s, 0);
        ctx.moveTo(0, -s);
        ctx.lineTo(0, s);
        ctx.stroke();
      } else {
        ctx.beginPath();
        ctx.arc(0, 0, Math.max(.45, s * .5), 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.restore();
    }
  }

  function setActive(next) {
    active = !!next;
    canvas.classList.toggle("active", active);
    glitterButton.classList.toggle("active", active);
    glitterButton.textContent = active ? "GLITTER ON" : "GLITTER OFF";
    if (active) buildFlakes(true);
    else ctx.clearRect(0, 0, width, height);
  }

  function applyGlitterPreset() {
    const values = {
      count: 420,
      speed: .42,
      trails: .86,
      links: 0,
      attraction: 0,
      repel: .08,
      noise: .62,
      swirl: .18,
      glow: 20,
      symmetry: 1,
      hue: 42,
      hueSpread: 145,
      pulse: .35,
      scale: 1.25
    };
    Object.entries(values).forEach(([key, value]) => setControl(key, value));
    setActive(true);
    revealUI();
  }

  // Click toggles the overlay. Shift-click reloads the built-in glitter preset.
  glitterButton.addEventListener("click", event => {
    if (event.shiftKey) applyGlitterPreset();
    else setActive(!active);
    revealUI();
  });

  // G toggles glitter; Shift+G reapplies the glitter preset.
  addEventListener("keydown", event => {
    if (["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement.tagName)) return;
    if (event.key.toLowerCase() === "g") {
      if (event.shiftKey) applyGlitterPreset();
      else setActive(!active);
    }
  });

  function hideUI() {
    document.body.classList.add("idle-clean");
  }

  function revealUI() {
    document.body.classList.remove("idle-clean");
    clearTimeout(idleTimer);
    idleTimer = setTimeout(hideUI, 5000);
  }

  ["pointermove", "pointerdown", "touchstart", "wheel", "keydown"].forEach(name => {
    addEventListener(name, revealUI, { passive: true });
  });
  if (panel) panel.addEventListener("input", revealUI);
  if (showPanel) showPanel.addEventListener("click", revealUI);

  function frame(t) {
    const dt = Math.min(40, Math.max(1, t - last));
    last = t;
    if (active) drawGlitter(t, dt);
    requestAnimationFrame(frame);
  }

  addEventListener("resize", resize);
  resize();
  revealUI();
  setActive(true);
  requestAnimationFrame(frame);
})();
