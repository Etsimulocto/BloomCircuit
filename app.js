(() => {
  "use strict";

  const NS = "http://www.w3.org/2000/svg";
  const GRID = 10;
  const MM_PER_PX = 0.254;
  const components = window.BLOOM_COMPONENTS;

  const canvas = document.getElementById("canvas");
  const wiresLayer = document.getElementById("wiresLayer");
  const componentsLayer = document.getElementById("componentsLayer");
  const palette = document.getElementById("palette");
  const netType = document.getElementById("netType");
  const projectName = document.getElementById("projectName");
  const statusEl = document.getElementById("status");
  const warningEl = document.getElementById("warning");
  const etchMode = document.getElementById("etchMode");
  const loadInput = document.getElementById("loadInput");

  const state = {
    components: [],
    wires: [],
    selected: null,
    pendingPin: null,
    drag: null,
    addCounter: 0
  };

  function uid(prefix) {
    return prefix + "_" + Date.now().toString(36) + "_" + Math.random().toString(36).slice(2, 8);
  }

  function snap(value) {
    return Math.round(value / GRID) * GRID;
  }

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  function svgEl(name, attrs) {
    const el = document.createElementNS(NS, name);
    Object.entries(attrs || {}).forEach(([key, value]) => {
      if (value !== null && value !== undefined) el.setAttribute(key, String(value));
    });
    return el;
  }

  function setStatus(message) {
    statusEl.textContent = message;
  }

  function setWarning(message) {
    warningEl.textContent = message || "";
  }

  function makeComponent(type, x, y, options) {
    const def = components[type];
    const opts = options || {};
    return {
      id: uid("cmp"),
      type,
      x: snap(x),
      y: snap(y),
      value: opts.value || (type === "resistor" ? "1K" : type === "capacitor" ? "104" : "")
    };
  }

  function addComponent(type) {
    const def = components[type];
    const offset = (state.addCounter % 8) * 30;
    state.addCounter += 1;
    const x = clamp(270 + offset, 10, 1180 - def.width);
    const y = clamp(90 + offset, 10, 680 - def.height);
    const comp = makeComponent(type, x, y);
    state.components.push(comp);
    state.selected = { kind: "component", id: comp.id };
    setStatus(def.title + " added.");
    render();
  }

  function getComponent(id) {
    return state.components.find(c => c.id === id) || null;
  }

  function getPinDef(comp, pinId) {
    if (!comp) return null;
    return components[comp.type].pins.find(p => p.id === pinId) || null;
  }

  function pinWorld(compId, pinId) {
    const comp = getComponent(compId);
    const pin = getPinDef(comp, pinId);
    if (!comp || !pin) return null;
    return { x: comp.x + pin.x, y: comp.y + pin.y };
  }

  function connectionLabel(pin, comp) {
    if (comp.type === "pi40") {
      if ([1, 2, 4, 6, 19].includes(pin.number)) return pin.number + " " + pin.name;
      return String(pin.number);
    }
    if (pin.number) return pin.number + " " + pin.name;
    return pin.name;
  }

  function addText(group, text, x, y, className, anchor) {
    const t = svgEl("text", {
      x,
      y,
      class: className,
      "text-anchor": anchor || "middle"
    });
    t.textContent = text;
    group.appendChild(t);
    return t;
  }

  function renderBody(group, comp, def) {
    if (def.kind === "bus") {
      const body = svgEl("rect", { x: 0, y: 0, width: def.width, height: def.height, rx: 8, class: "component-body" });
      group.appendChild(body);
      group.appendChild(svgEl("line", { x1: 10, y1: 30, x2: def.width - 10, y2: 30, class: "bus-line" }));
      return body;
    }

    if (def.kind === "resistor") {
      group.appendChild(svgEl("line", { x1: 0, y1: 25, x2: 32, y2: 25, class: "bus-line" }));
      group.appendChild(svgEl("line", { x1: 88, y1: 25, x2: 120, y2: 25, class: "bus-line" }));
      const body = svgEl("rect", { x: 32, y: 10, width: 56, height: 30, rx: 7, class: "resistor-body component-body" });
      group.appendChild(body);
      return body;
    }

    if (def.kind === "capacitor") {
      const body = svgEl("rect", { x: 0, y: 0, width: def.width, height: def.height, rx: 8, class: "component-body" });
      group.appendChild(body);
      group.appendChild(svgEl("line", { x1: 35, y1: 0, x2: 35, y2: 27, class: "bus-line" }));
      group.appendChild(svgEl("line", { x1: 15, y1: 32, x2: 55, y2: 32, class: "cap-plate" }));
      group.appendChild(svgEl("line", { x1: 15, y1: 44, x2: 55, y2: 44, class: "cap-plate" }));
      group.appendChild(svgEl("line", { x1: 35, y1: 49, x2: 35, y2: 80, class: "bus-line" }));
      return body;
    }

    if (def.kind === "led") {
      const body = svgEl("rect", { x: 0, y: 0, width: def.width, height: def.height, rx: 10, class: "component-body" });
      group.appendChild(body);
      group.appendChild(svgEl("circle", { cx: 60, cy: 55, r: 27, class: "led-lens" }));
      return body;
    }

    if (def.kind === "node") {
      const body = svgEl("circle", { cx: 28, cy: 28, r: 24, class: "component-body" });
      group.appendChild(body);
      return body;
    }

    const body = svgEl("rect", { x: 0, y: 0, width: def.width, height: def.height, rx: 9, class: "component-body" });
    group.appendChild(body);

    if (def.kind === "dip") {
      group.appendChild(svgEl("path", {
        d: "M " + (def.width / 2 - 14) + " 0 A 14 14 0 0 0 " + (def.width / 2 + 14) + " 0",
        fill: "none",
        stroke: "#252b30",
        "stroke-width": 2
      }));
    }
    return body;
  }

  function renderPin(group, comp, pin) {
    const circle = svgEl("circle", {
      cx: pin.x,
      cy: pin.y,
      r: 5,
      class: "pin" + (state.pendingPin && state.pendingPin.compId === comp.id && state.pendingPin.pinId === pin.id ? " pending" : ""),
      "data-comp-id": comp.id,
      "data-pin-id": pin.id
    });

    circle.addEventListener("pointerdown", e => e.stopPropagation());
    circle.addEventListener("click", e => {
      e.stopPropagation();
      handlePinClick(comp.id, pin.id);
    });
    group.appendChild(circle);

    let x = pin.x;
    let y = pin.y + 3;
    let anchor = "middle";

    if (pin.side === "left") {
      x += 9;
      anchor = "start";
    } else if (pin.side === "right") {
      x -= 9;
      anchor = "end";
    } else if (pin.side === "top") {
      y += 14;
    } else if (pin.side === "bottom") {
      y -= 9;
    }

    addText(group, connectionLabel(pin, comp), x, y, "pin-label", anchor);
  }

  function renderComponent(comp) {
    const def = components[comp.type];
    const group = svgEl("g", {
      class: "component" + (state.selected && state.selected.kind === "component" && state.selected.id === comp.id ? " selected" : ""),
      transform: "translate(" + comp.x + " " + comp.y + ")",
      "data-id": comp.id
    });

    renderBody(group, comp, def);

    const titleY = def.kind === "pi40" ? 20 : 18;
    addText(group, def.title, def.width / 2, titleY, "component-title");

    if (comp.value) {
      addText(group, comp.value, def.width / 2, titleY + 14, "component-subtitle");
    } else if (def.subtitle && def.kind !== "pi40") {
      addText(group, def.subtitle, def.width / 2, titleY + 14, "component-subtitle");
    }

    def.pins.forEach(pin => renderPin(group, comp, pin));

    group.addEventListener("pointerdown", e => beginDrag(e, comp.id));
    group.addEventListener("click", e => {
      if (e.target.classList.contains("pin")) return;
      state.selected = { kind: "component", id: comp.id };
      setStatus(def.title + " selected.");
      render();
    });

    group.addEventListener("dblclick", e => {
      if (e.target.classList.contains("pin")) return;
      e.stopPropagation();
      const next = window.prompt("Component label/value:", comp.value || "");
      if (next !== null) {
        comp.value = next.trim();
        render();
      }
    });

    componentsLayer.appendChild(group);
  }

  function wirePath(a, b) {
    const dx = Math.abs(b.x - a.x);
    if (dx > 50) {
      const mx = snap((a.x + b.x) / 2);
      return "M " + a.x + " " + a.y + " H " + mx + " V " + b.y + " H " + b.x;
    }
    const my = snap((a.y + b.y) / 2);
    return "M " + a.x + " " + a.y + " V " + my + " H " + b.x + " V " + b.y;
  }

  function renderWire(wire) {
    const a = pinWorld(wire.from.compId, wire.from.pinId);
    const b = pinWorld(wire.to.compId, wire.to.pinId);
    if (!a || !b) return;

    const path = svgEl("path", {
      d: wirePath(a, b),
      class: "wire net-" + wire.net + (state.selected && state.selected.kind === "wire" && state.selected.id === wire.id ? " selected" : ""),
      "data-id": wire.id
    });

    path.addEventListener("pointerdown", e => e.stopPropagation());
    path.addEventListener("click", e => {
      e.stopPropagation();
      state.selected = { kind: "wire", id: wire.id };
      setStatus(wire.net + " wire selected.");
      render();
    });
    wiresLayer.appendChild(path);

    const tx = snap((a.x + b.x) / 2);
    const ty = snap((a.y + b.y) / 2) - 5;
    const label = svgEl("text", { x: tx, y: ty, class: "wire-label", "text-anchor": "middle" });
    label.textContent = wire.net;
    wiresLayer.appendChild(label);
  }

  function render() {
    wiresLayer.replaceChildren();
    componentsLayer.replaceChildren();
    state.wires.forEach(renderWire);
    state.components.forEach(renderComponent);
  }

  function describePin(ref) {
    const comp = getComponent(ref.compId);
    const pin = getPinDef(comp, ref.pinId);
    if (!comp || !pin) return "unknown pin";
    return components[comp.type].title + " / " + connectionLabel(pin, comp);
  }

  function safetyWarning(from, to, net) {
    const aComp = getComponent(from.compId);
    const bComp = getComponent(to.compId);
    const a = getPinDef(aComp, from.pinId);
    const b = getPinDef(bComp, to.pinId);
    const roles = [a && a.role, b && b.role];

    if (net === "5V" && roles.some(role => role === "gpio" || role === "3v3" || role === "gnd")) {
      return "WARNING: 5V net touches a GPIO, 3V3, or GND pin. Verify before powering.";
    }
    if (net === "GND" && roles.some(role => role === "5v" || role === "3v3")) {
      return "WARNING: GND net touches a power pin. Verify before powering.";
    }
    if (net === "3V3" && roles.some(role => role === "5v" || role === "gnd")) {
      return "WARNING: 3V3 net touches 5V or GND. Verify before powering.";
    }
    return "";
  }

  function handlePinClick(compId, pinId) {
    const ref = { compId, pinId };

    if (!state.pendingPin) {
      state.pendingPin = ref;
      setWarning("");
      setStatus("Start: " + describePin(ref) + ". Choose destination pin.");
      render();
      return;
    }

    if (state.pendingPin.compId === compId && state.pendingPin.pinId === pinId) {
      state.pendingPin = null;
      setStatus("Wire cancelled.");
      render();
      return;
    }

    const net = netType.value;
    const exists = state.wires.some(w =>
      ((w.from.compId === state.pendingPin.compId && w.from.pinId === state.pendingPin.pinId && w.to.compId === compId && w.to.pinId === pinId) ||
       (w.to.compId === state.pendingPin.compId && w.to.pinId === state.pendingPin.pinId && w.from.compId === compId && w.from.pinId === pinId))
    );

    if (!exists) {
      const wire = {
        id: uid("wire"),
        from: { ...state.pendingPin },
        to: ref,
        net
      };
      state.wires.push(wire);
      state.selected = { kind: "wire", id: wire.id };
      setWarning(safetyWarning(wire.from, wire.to, net));
      setStatus(net + " wire created: " + describePin(wire.from) + " -> " + describePin(wire.to));
    } else {
      setStatus("Those pins are already connected.");
    }

    state.pendingPin = null;
    render();
  }

  function clientToSvg(e) {
    const point = canvas.createSVGPoint();
    point.x = e.clientX;
    point.y = e.clientY;
    const matrix = canvas.getScreenCTM();
    if (!matrix) return { x: 0, y: 0 };
    return point.matrixTransform(matrix.inverse());
  }

  function beginDrag(e, compId) {
    if (e.button !== undefined && e.button !== 0) return;
    if (e.target.classList.contains("pin")) return;

    const comp = getComponent(compId);
    if (!comp) return;

    const p = clientToSvg(e);
    state.drag = {
      pointerId: e.pointerId,
      compId,
      dx: p.x - comp.x,
      dy: p.y - comp.y
    };
    state.selected = { kind: "component", id: compId };
    canvas.setPointerCapture(e.pointerId);
    e.preventDefault();
  }

  canvas.addEventListener("pointermove", e => {
    if (!state.drag || e.pointerId !== state.drag.pointerId) return;
    const comp = getComponent(state.drag.compId);
    if (!comp) return;
    const def = components[comp.type];
    const p = clientToSvg(e);
    comp.x = snap(clamp(p.x - state.drag.dx, 0, 1200 - def.width));
    comp.y = snap(clamp(p.y - state.drag.dy, 0, 700 - def.height));
    render();
  });

  canvas.addEventListener("pointerup", e => {
    if (!state.drag || e.pointerId !== state.drag.pointerId) return;
    try { canvas.releasePointerCapture(e.pointerId); } catch (_) {}
    state.drag = null;
    setStatus("Component moved.");
  });

  canvas.addEventListener("click", e => {
    if (e.target === canvas || e.target.id === "grid-bg") {
      state.selected = null;
      render();
    }
  });

  function deleteSelected() {
    if (!state.selected) {
      setStatus("Nothing selected.");
      return;
    }

    if (state.selected.kind === "component") {
      const id = state.selected.id;
      state.components = state.components.filter(c => c.id !== id);
      state.wires = state.wires.filter(w => w.from.compId !== id && w.to.compId !== id);
    } else {
      state.wires = state.wires.filter(w => w.id !== state.selected.id);
    }

    state.selected = null;
    state.pendingPin = null;
    setStatus("Deleted.");
    render();
  }

  function download(name, content, mime) {
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function cleanFileName(value) {
    const cleaned = String(value || "bloomcircuit")
      .trim()
      .replace(/[^a-z0-9_-]+/gi, "_")
      .replace(/^_+|_+$/g, "");
    return cleaned || "bloomcircuit";
  }

  function saveProject() {
    const data = {
      format: "BloomCircuit",
      version: 1,
      projectName: projectName.value.trim() || "BloomCircuit",
      gridPx: GRID,
      mmPerPx: MM_PER_PX,
      components: state.components,
      wires: state.wires
    };
    download(cleanFileName(data.projectName) + ".json", JSON.stringify(data, null, 2), "application/json");
    setStatus("Project JSON saved.");
  }

  function validateLoaded(data) {
    if (!data || !Array.isArray(data.components) || !Array.isArray(data.wires)) {
      throw new Error("Not a BloomCircuit project.");
    }

    const goodComponents = data.components.filter(c =>
      c && typeof c.id === "string" && components[c.type] &&
      Number.isFinite(Number(c.x)) && Number.isFinite(Number(c.y))
    ).map(c => ({
      id: c.id,
      type: c.type,
      x: snap(Number(c.x)),
      y: snap(Number(c.y)),
      value: typeof c.value === "string" ? c.value : ""
    }));

    const validIds = new Set(goodComponents.map(c => c.id));
    const goodWires = data.wires.filter(w =>
      w && typeof w.id === "string" &&
      w.from && w.to &&
      validIds.has(w.from.compId) && validIds.has(w.to.compId) &&
      ["5V", "3V3", "GND", "DATA", "OTHER"].includes(w.net)
    );

    return { components: goodComponents, wires: goodWires };
  }

  async function loadProject(file) {
    try {
      const text = await file.text();
      const data = JSON.parse(text);
      const checked = validateLoaded(data);
      state.components = checked.components;
      state.wires = checked.wires;
      state.selected = null;
      state.pendingPin = null;
      projectName.value = data.projectName || "BloomCircuit";
      setWarning("");
      setStatus("Project loaded.");
      render();
    } catch (err) {
      setWarning("Load failed: " + err.message);
    }
  }

  function exportSvg() {
    render();

    const clone = canvas.cloneNode(true);
    const grid = clone.querySelector("#grid-bg");
    if (grid) grid.remove();

    clone.querySelectorAll(".selected").forEach(el => el.classList.remove("selected"));
    clone.querySelectorAll(".pending").forEach(el => el.classList.remove("pending"));

    clone.setAttribute("xmlns", NS);
    clone.setAttribute("width", (1200 * MM_PER_PX).toFixed(2) + "mm");
    clone.setAttribute("height", (700 * MM_PER_PX).toFixed(2) + "mm");
    clone.setAttribute("viewBox", "0 0 1200 700");

    const style = document.createElementNS(NS, "style");
    const monochrome = etchMode.checked;

    style.textContent =
      ".component-body,.resistor-body,.led-lens{fill:#fff;stroke:#000;stroke-width:2}" +
      ".component-title{fill:#000;font:700 12px sans-serif;text-anchor:middle}" +
      ".component-subtitle,.pin-label{fill:#000;font:9px sans-serif}" +
      ".pin{fill:#fff;stroke:#000;stroke-width:1.3}" +
      ".bus-line,.cap-plate{stroke:#000;fill:none}" +
      ".wire{fill:none;stroke-width:4;stroke-linejoin:round;stroke-linecap:round}" +
      ".wire-label{fill:#000;font:700 9px sans-serif;paint-order:stroke;stroke:#fff;stroke-width:3}" +
      (monochrome
        ? ".wire{stroke:#000}"
        : ".net-5V{stroke:#e53935}.net-3V3{stroke:#ef8c2f}.net-GND{stroke:#606b75}.net-DATA{stroke:#1976d2}.net-OTHER{stroke:#7b4ab5}");

    let defs = clone.querySelector("defs");
    if (!defs) {
      defs = document.createElementNS(NS, "defs");
      clone.insertBefore(defs, clone.firstChild);
    }
    defs.appendChild(style);

    const xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + new XMLSerializer().serializeToString(clone);
    download(cleanFileName(projectName.value) + (monochrome ? "_ETCH" : "") + ".svg", xml, "image/svg+xml");
    setStatus("SVG exported at 10 px = 2.54 mm.");
  }

  function addTemplateWire(fromComp, fromPin, toComp, toPin, net) {
    state.wires.push({
      id: uid("wire"),
      from: { compId: fromComp.id, pinId: fromPin },
      to: { compId: toComp.id, pinId: toPin },
      net
    });
  }

  function loadHappyJarz() {
    state.components = [];
    state.wires = [];
    state.selected = null;
    state.pendingPin = null;

    const pi = makeComponent("pi40", 20, 130);
    const bus5 = makeComponent("bus5", 340, 45);
    const busg = makeComponent("busg", 340, 605);
    const chip = makeComponent("ahct125", 400, 185);
    const resistor = makeComponent("resistor", 620, 265, { value: "1K" });
    const led1 = makeComponent("apa106", 790, 180, { value: "LED #1" });
    const led2 = makeComponent("apa106", 1010, 180, { value: "LED #2" });
    const capChip = makeComponent("capacitor", 500, 470, { value: "104" });
    const cap1 = makeComponent("capacitor", 820, 430, { value: "104" });
    const cap2 = makeComponent("capacitor", 1040, 430, { value: "104" });

    state.components.push(pi, bus5, busg, chip, resistor, led1, led2, capChip, cap1, cap2);

    addTemplateWire(pi, "p02", bus5, "t1", "5V");
    addTemplateWire(pi, "p06", busg, "t1", "GND");
    addTemplateWire(pi, "p19", chip, "p2", "DATA");

    addTemplateWire(chip, "p14", bus5, "t2", "5V");
    addTemplateWire(chip, "p7", busg, "t2", "GND");
    addTemplateWire(chip, "p1", busg, "t3", "GND");

    addTemplateWire(chip, "p3", resistor, "a", "DATA");
    addTemplateWire(resistor, "b", led1, "din", "DATA");
    addTemplateWire(led1, "dout", led2, "din", "DATA");

    addTemplateWire(led1, "vdd", bus5, "t3", "5V");
    addTemplateWire(led1, "gnd", busg, "t4", "GND");
    addTemplateWire(led2, "vdd", bus5, "t4", "5V");
    addTemplateWire(led2, "gnd", busg, "t5", "GND");

    addTemplateWire(capChip, "a", bus5, "t5", "5V");
    addTemplateWire(capChip, "b", busg, "t6", "GND");
    addTemplateWire(cap1, "a", bus5, "t6", "5V");
    addTemplateWire(cap1, "b", busg, "t7", "GND");
    addTemplateWire(cap2, "a", bus5, "t7", "5V");
    addTemplateWire(cap2, "b", busg, "t8", "GND");

    addTemplateWire(chip, "p4", bus5, "t8", "5V");
    addTemplateWire(chip, "p10", bus5, "t9", "5V");
    addTemplateWire(chip, "p13", bus5, "t10", "5V");
    addTemplateWire(chip, "p5", busg, "t9", "GND");
    addTemplateWire(chip, "p9", busg, "t10", "GND");
    addTemplateWire(chip, "p12", busg, "t11", "GND");

    projectName.value = "Happy Jarz Circuit";
    setWarning("");
    setStatus("Happy Jarz starter circuit loaded.");
    render();
  }

  function buildPalette() {
    Object.entries(components).forEach(([type, def]) => {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = "+ " + def.palette;
      button.addEventListener("click", () => addComponent(type));
      palette.appendChild(button);
    });
  }

  document.getElementById("happyJarzBtn").addEventListener("click", loadHappyJarz);
  document.getElementById("saveBtn").addEventListener("click", saveProject);
  document.getElementById("loadBtn").addEventListener("click", () => loadInput.click());
  document.getElementById("exportBtn").addEventListener("click", exportSvg);
  document.getElementById("deleteBtn").addEventListener("click", deleteSelected);

  document.getElementById("clearBtn").addEventListener("click", () => {
    if (!window.confirm("Clear the entire BloomCircuit canvas?")) return;
    state.components = [];
    state.wires = [];
    state.selected = null;
    state.pendingPin = null;
    setWarning("");
    setStatus("Canvas cleared.");
    render();
  });

  loadInput.addEventListener("change", () => {
    const file = loadInput.files && loadInput.files[0];
    if (file) loadProject(file);
    loadInput.value = "";
  });

  etchMode.addEventListener("change", () => {
    document.body.classList.toggle("etch-mode", etchMode.checked);
    setStatus(etchMode.checked ? "Etch view enabled." : "Color wiring view enabled.");
  });

  document.addEventListener("keydown", e => {
    const tag = document.activeElement && document.activeElement.tagName;
    if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;

    if (e.key === "Delete" || e.key === "Backspace") {
      e.preventDefault();
      deleteSelected();
    } else if (e.key === "Escape") {
      state.pendingPin = null;
      state.selected = null;
      setWarning("");
      setStatus("Selection cancelled.");
      render();
    }
  });

  buildPalette();
  loadHappyJarz();
})();
