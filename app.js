(() => {
  "use strict";

  const NS = "http://www.w3.org/2000/svg";
  const GRID = 10;
  const MM_PER_PX = 0.254;
  const CANVAS_WIDTH = 3000;
  const CANVAS_HEIGHT = 1800;
  const library = window.BloomLibrary;
  const components = library.components;
  const BUILTIN_IDS = new Set(Object.keys(components));

  const canvas = document.getElementById("canvas");
  const boardsLayer = document.getElementById("boardsLayer");
  const wiresLayer = document.getElementById("wiresLayer");
  const componentsLayer = document.getElementById("componentsLayer");
  const palette = document.getElementById("palette");
  const paletteEmpty = document.getElementById("paletteEmpty");
  const componentSearch = document.getElementById("componentSearch");
  const categoryFilter = document.getElementById("categoryFilter");
  const libraryCount = document.getElementById("libraryCount");
  const netType = document.getElementById("netType");
  const projectName = document.getElementById("projectName");
  const statusEl = document.getElementById("status");
  const warningEl = document.getElementById("warning");
  const etchMode = document.getElementById("etchMode");
  const loadInput = document.getElementById("loadInput");
  const packInput = document.getElementById("packInput");

  const componentDialog = document.getElementById("componentDialog");
  const componentForm = document.getElementById("componentForm");
  const componentFormError = document.getElementById("componentFormError");
  const customId = document.getElementById("customId");
  const customTitle = document.getElementById("customTitle");
  const customCategory = document.getElementById("customCategory");
  const customKind = document.getElementById("customKind");
  const customWidth = document.getElementById("customWidth");
  const customHeight = document.getElementById("customHeight");
  const customSubtitle = document.getElementById("customSubtitle");
  const customPins = document.getElementById("customPins");
  const customImageInput = document.getElementById("customImageInput");
  const customFootprintPreview = document.getElementById("customFootprintPreview");
  const customFootprintImage = document.getElementById("customFootprintImage");
  const customFootprintPins = document.getElementById("customFootprintPins");
  const customMakerGridBg = document.getElementById("customMakerGridBg");
  const customMakerSize = document.getElementById("customMakerSize");
  const customPinEmpty = document.getElementById("customPinEmpty");
  const customPinEditor = document.getElementById("customPinEditor");
  const customPinId = document.getElementById("customPinId");
  const customPinLabel = document.getElementById("customPinLabel");
  const customPinRole = document.getElementById("customPinRole");
  const customPinX = document.getElementById("customPinX");
  const customPinY = document.getElementById("customPinY");
  const customPinList = document.getElementById("customPinList");

  const selectionKind = document.getElementById("selectionKind");
  const selectionName = document.getElementById("selectionName");
  const componentTools = document.getElementById("componentTools");
  const wireTools = document.getElementById("wireTools");
  const componentColor = document.getElementById("componentColor");
  const componentTextColor = document.getElementById("componentTextColor");
  const componentScale = document.getElementById("componentScale");
  const componentFontSize = document.getElementById("componentFontSize");
  const componentFontSizeOut = document.getElementById("componentFontSizeOut");
  const wireNetType = document.getElementById("wireNetType");
  const wireColor = document.getElementById("wireColor");
  const wireWidth = document.getElementById("wireWidth");
  const wireWidthOut = document.getElementById("wireWidthOut");
  const wireNoteTools = document.getElementById("wireNoteTools");
  const wireNoteText = document.getElementById("wireNoteText");
  const wireNoteColor = document.getElementById("wireNoteColor");
  const wireNoteFontSize = document.getElementById("wireNoteFontSize");
  const wireNoteFontSizeOut = document.getElementById("wireNoteFontSizeOut");

  const boardType = document.getElementById("boardType");
  const boardHolesX = document.getElementById("boardHolesX");
  const boardHolesY = document.getElementById("boardHolesY");
  const boardTools = document.getElementById("boardTools");
  const selectedBoardType = document.getElementById("selectedBoardType");
  const selectedBoardHolesX = document.getElementById("selectedBoardHolesX");
  const selectedBoardHolesY = document.getElementById("selectedBoardHolesY");
  const boardScale = document.getElementById("boardScale");
  const boardColor = document.getElementById("boardColor");
  const boardHoleColor = document.getElementById("boardHoleColor");

  const canvasBgColor = document.getElementById("canvasBgColor");
  const minorGridColor = document.getElementById("minorGridColor");
  const majorGridColor = document.getElementById("majorGridColor");
  const pinFontSize = document.getElementById("pinFontSize");
  const pinFontSizeOut = document.getElementById("pinFontSizeOut");
  const zoomRange = document.getElementById("zoomRange");
  const zoomOut = document.getElementById("zoomOut");

  const NET_COLORS = {
    "5V":"#ff6b6b",
    "3V3":"#f7b267",
    "GND":"#7f8c98",
    "DATA":"#6cb6ff",
    "OTHER":"#c792ea"
  };

  const CANVAS_DEFAULTS = {
    bgColor:"#f8f5ed",
    minorGridColor:"#d9d5cc",
    majorGridColor:"#b9b4aa",
    pinFontSize:8,
    zoom:1
  };

  const state = {
    boards: [],
    components: [],
    wires: [],
    selected: null,
    pendingPin: null,
    drag: null,
    suppressCanvasClick: false,
    addCounter: 0,
    customIds: new Set(),
    canvasSettings: { ...CANVAS_DEFAULTS }
  };

  const customMaker = {
    pins: [],
    selectedIndex: -1,
    dragIndex: -1,
    imageData: ""
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

  function cleanFileName(value) {
    const cleaned = String(value || "bloomcircuit")
      .trim()
      .replace(/[^a-z0-9_-]+/gi, "_")
      .replace(/^_+|_+$/g, "");
    return cleaned || "bloomcircuit";
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

  function saveCustomLibraryLocal() {
    try {
      const ids = Array.from(state.customIds).filter(id => components[id]);
      localStorage.setItem("BloomCircuit.customPack", JSON.stringify(library.exportPack(ids)));
    } catch (_) {
      // App still works without browser storage.
    }
  }

  function loadCustomLibraryLocal() {
    try {
      const raw = localStorage.getItem("BloomCircuit.customPack");
      if (!raw) return;
      const pack = JSON.parse(raw);
      library.registerPack(pack, true);
      (pack.components || []).forEach(item => state.customIds.add(item.id));
    } catch (_) {
      // Ignore malformed/blocked local storage.
    }
  }

  function makeComponent(type, x, y, options) {
    const def = components[type];
    if (!def) throw new Error("Unknown component: " + type);
    const opts = options || {};
    return {
      id: uid("cmp"),
      type,
      x: snap(x),
      y: snap(y),
      rotation: Number(opts.rotation) || 0,
      scale: clamp(Number(opts.scale) || 1, .25, 4),
      value: opts.value !== undefined ? opts.value : (def.defaultValue || ""),
      fillColor: opts.fillColor || null,
      textColor: opts.textColor || null,
      fontSize: Number(opts.fontSize) || 12
    };
  }

  function addComponent(type) {
    const def = components[type];
    if (!def) return;
    const offset = (state.addCounter % 8) * 30;
    state.addCounter += 1;
    const x = clamp(300 + offset, 10, CANVAS_WIDTH - 20 - def.width);
    const y = clamp(80 + offset, 10, CANVAS_HEIGHT - 20 - def.height);
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
    if (!comp || !components[comp.type]) return null;
    return components[comp.type].pins.find(p => p.id === pinId) || null;
  }

  function pinWorld(compId, pinId) {
    const comp = getComponent(compId);
    const pin = getPinDef(comp, pinId);
    if (!comp || !pin) return null;
    const def = components[comp.type];
    const angle = ((Number(comp.rotation) || 0) % 360 + 360) % 360;
    const scale = clamp(Number(comp.scale) || 1,.1,10);

    const cx = def.width / 2;
    const cy = def.height / 2;
    const rad = angle * Math.PI / 180;
    const dx = (pin.x - cx) * scale;
    const dy = (pin.y - cy) * scale;
    return {
      x: comp.x + cx + dx * Math.cos(rad) - dy * Math.sin(rad),
      y: comp.y + cy + dx * Math.sin(rad) + dy * Math.cos(rad)
    };
  }

  function connectionLabel(pinDef, comp) {
    if (comp.type === "pi40") {
      if ([1,2,4,6,19].includes(pinDef.number)) return pinDef.number + " " + pinDef.name;
      return String(pinDef.number);
    }
    if (pinDef.number) return pinDef.number + " " + pinDef.name;
    return pinDef.name;
  }

  function addText(group, value, x, y, className, anchor) {
    const t = svgEl("text", {
      x, y, class: className,
      "text-anchor": anchor || "middle"
    });
    t.textContent = value;
    group.appendChild(t);
    return t;
  }

  function renderBody(group, comp, def) {
    if (def.imageData) {
      const body = svgEl("rect", { x:0,y:0,width:def.width,height:def.height,rx:6,class:"component-body" });
      group.appendChild(body);
      const image = svgEl("image", {
        x:0,y:0,width:def.width,height:def.height,
        href:def.imageData,
        preserveAspectRatio:"none",
        class:"component-image"
      });
      group.appendChild(image);
      return body;
    }

    if (def.kind === "bus") {
      const body = svgEl("rect", { x:0,y:0,width:def.width,height:def.height,rx:8,class:"component-body" });
      group.appendChild(body);
      group.appendChild(svgEl("line", { x1:10,y1:30,x2:def.width-10,y2:30,class:"bus-line" }));
      return body;
    }

    if (def.kind === "resistor") {
      group.appendChild(svgEl("line", { x1:0,y1:def.height/2,x2:32,y2:def.height/2,class:"bus-line" }));
      group.appendChild(svgEl("line", { x1:def.width-32,y1:def.height/2,x2:def.width,y2:def.height/2,class:"bus-line" }));
      const body = svgEl("rect", { x:32,y:10,width:def.width-64,height:def.height-20,rx:7,class:"resistor-body component-body" });
      group.appendChild(body);
      return body;
    }

    if (def.kind === "capacitor") {
      const body = svgEl("rect", { x:0,y:0,width:def.width,height:def.height,rx:8,class:"component-body" });
      group.appendChild(body);
      const cx = def.width / 2;
      const mid = def.height / 2;
      group.appendChild(svgEl("line", { x1:cx,y1:0,x2:cx,y2:mid-13,class:"bus-line" }));
      group.appendChild(svgEl("line", { x1:cx-20,y1:mid-7,x2:cx+20,y2:mid-7,class:"cap-plate" }));
      group.appendChild(svgEl("line", { x1:cx-20,y1:mid+7,x2:cx+20,y2:mid+7,class:"cap-plate" }));
      group.appendChild(svgEl("line", { x1:cx,y1:mid+13,x2:cx,y2:def.height,class:"bus-line" }));
      return body;
    }

    if (def.kind === "led") {
      const body = svgEl("rect", { x:0,y:0,width:def.width,height:def.height,rx:10,class:"component-body" });
      group.appendChild(body);
      group.appendChild(svgEl("circle", { cx:def.width/2,cy:def.height/2,r:Math.min(28,Math.min(def.width,def.height)/3),class:"led-lens" }));
      return body;
    }

    if (def.kind === "node") {
      const body = svgEl("circle", { cx:def.width/2,cy:def.height/2,r:Math.min(def.width,def.height)/2-4,class:"component-body" });
      group.appendChild(body);
      return body;
    }

    const body = svgEl("rect", { x:0,y:0,width:def.width,height:def.height,rx:9,class:"component-body" });
    group.appendChild(body);

    if (def.kind === "dip") {
      group.appendChild(svgEl("path", {
        d:"M " + (def.width/2-14) + " 0 A 14 14 0 0 0 " + (def.width/2+14) + " 0",
        fill:"none", stroke:"#252b30", "stroke-width":2
      }));
    }
    return body;
  }

  function renderPin(group, comp, pinDef) {
    const circle = svgEl("circle", {
      cx: pinDef.x,
      cy: pinDef.y,
      r: 5,
      class: "pin" + (state.pendingPin && state.pendingPin.compId === comp.id && state.pendingPin.pinId === pinDef.id ? " pending" : ""),
      "data-comp-id": comp.id,
      "data-pin-id": pinDef.id
    });

    circle.addEventListener("pointerdown", e => e.stopPropagation());
    circle.addEventListener("click", e => {
      e.stopPropagation();
      handlePinClick(comp.id, pinDef.id);
    });
    group.appendChild(circle);

    let x = pinDef.x;
    let y = pinDef.y + 3;
    let anchor = "middle";

    if (pinDef.side === "left") {
      x += 9; anchor = "start";
    } else if (pinDef.side === "right") {
      x -= 9; anchor = "end";
    } else if (pinDef.side === "top") {
      y += 14;
    } else if (pinDef.side === "bottom") {
      y -= 9;
    }

    addText(group, connectionLabel(pinDef, comp), x, y, "pin-label", anchor);
  }

  function renderComponent(comp) {
    const def = components[comp.type];
    if (!def) return;

    const subtitleSize = Math.max(6, (Number(comp.fontSize) || 12) - 3);
    const group = svgEl("g", {
      class: "component" + (state.selected && state.selected.kind === "component" && state.selected.id === comp.id ? " selected" : ""),
      transform: "translate(" + comp.x + " " + comp.y + ") translate(" + (def.width/2) + " " + (def.height/2) + ") rotate(" + (Number(comp.rotation) || 0) + ") scale(" + clamp(Number(comp.scale) || 1,.1,10) + ") translate(" + (-def.width/2) + " " + (-def.height/2) + ")",
      style: "--component-fill:" + (comp.fillColor || defaultComponentFill(def.kind)) + ";--component-text:" + (comp.textColor || "#191d20") + ";--component-font-size:" + (Number(comp.fontSize) || 12) + "px;--component-subtitle-size:" + subtitleSize + "px",
      "data-id": comp.id
    });

    renderBody(group, comp, def);

    const titleY = def.kind === "pi40" ? 20 : 18;
    addText(group, def.title, def.width / 2, titleY, "component-title");

    if (comp.value) {
      addText(group, comp.value, def.width / 2, titleY + 14, "component-subtitle");
    } else if (def.subtitle && comp.type !== "pi40") {
      addText(group, def.subtitle, def.width / 2, titleY + 14, "component-subtitle");
    }

    def.pins.forEach(pinDef => renderPin(group, comp, pinDef));

    group.addEventListener("pointerdown", e => beginDrag(e, comp.id));
    group.addEventListener("click", e => {
      if (e.target.classList.contains("pin")) return;
      state.selected = { kind:"component", id:comp.id };
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

  function blankWireNotes() {
    return {
      from:{ text:"", color:"#24282c", fontSize:10 },
      to:{ text:"", color:"#24282c", fontSize:10 }
    };
  }

  function ensureWireNotes(wire) {
    if (!wire.notes || typeof wire.notes !== "object") wire.notes = blankWireNotes();
    ["from","to"].forEach(end => {
      const current = wire.notes[end];
      if (!current || typeof current !== "object") {
        wire.notes[end] = { text:"", color:"#24282c", fontSize:10 };
        return;
      }
      current.text = typeof current.text === "string" ? current.text : "";
      current.color = typeof current.color === "string" ? current.color : "#24282c";
      current.fontSize = clamp(Number(current.fontSize) || 10,6,30);
    });
    return wire.notes;
  }

  function selectWireNote(wireId,end) {
    state.selected = { kind:"wireNote", id:wireId, end };
    setStatus((end === "from" ? "Start" : "End") + " wire note selected.");
    render();
  }

  function renderEndpointNote(wire,end,point,other,isWireSelected) {
    const note = ensureWireNotes(wire)[end];
    const dir = other.x >= point.x ? 1 : -1;
    const x = point.x + dir * 14;
    const y = point.y - 12;
    const anchor = dir > 0 ? "start" : "end";
    const noteSelected = state.selected && state.selected.kind === "wireNote" &&
      state.selected.id === wire.id && state.selected.end === end;

    if (note.text.trim()) {
      const textEl = svgEl("text", {
        x,y,
        class:"wire-note",
        "text-anchor":anchor,
        style:"fill:" + note.color + ";font-size:" + note.fontSize + "px",
        "data-wire-id":wire.id,
        "data-wire-end":end
      });

      note.text.split(/\r?\n/).slice(0,8).forEach((line,index) => {
        const tspan = svgEl("tspan", {
          x,
          dy:index === 0 ? 0 : note.fontSize * 1.2
        });
        tspan.textContent = line;
        textEl.appendChild(tspan);
      });

      textEl.addEventListener("pointerdown",e => e.stopPropagation());
      textEl.addEventListener("click",e => {
        e.stopPropagation();
        selectWireNote(wire.id,end);
      });
      wiresLayer.appendChild(textEl);
    }

    if (isWireSelected || noteSelected) {
      const hx = point.x + dir * 10;
      const hy = point.y + 11;
      const handle = svgEl("circle", {
        cx:hx,cy:hy,r:8,
        class:"wire-note-handle",
        "data-wire-id":wire.id,
        "data-wire-end":end
      });
      handle.addEventListener("pointerdown",e => e.stopPropagation());
      handle.addEventListener("click",e => {
        e.stopPropagation();
        selectWireNote(wire.id,end);
      });
      wiresLayer.appendChild(handle);

      const plus = svgEl("text", {
        x:hx,y:hy + .5,
        class:"wire-note-plus"
      });
      plus.textContent = note.text.trim() ? "✎" : "+";
      wiresLayer.appendChild(plus);
    }
  }

  function renderWire(wire) {
    const a = pinWorld(wire.from.compId, wire.from.pinId);
    const b = pinWorld(wire.to.compId, wire.to.pinId);
    if (!a || !b) return;

    const isWireSelected = state.selected &&
      (state.selected.kind === "wire" || state.selected.kind === "wireNote") &&
      state.selected.id === wire.id;
    const baseWidth = clamp(Number(wire.width) || 4, 1, 12);
    const path = svgEl("path", {
      d: wirePath(a,b),
      class: "wire net-" + wire.net + (isWireSelected ? " selected" : ""),
      style: "stroke:" + (wire.color || NET_COLORS[wire.net] || NET_COLORS.OTHER) + ";stroke-width:" + (isWireSelected ? baseWidth + 3 : baseWidth),
      "data-id": wire.id
    });

    path.addEventListener("pointerdown", e => e.stopPropagation());
    path.addEventListener("click", e => {
      e.stopPropagation();
      state.selected = { kind:"wire", id:wire.id };
      setStatus("Wire selected — use + at either end for notes.");
      render();
    });
    wiresLayer.appendChild(path);

    // No automatic center label. Endpoint annotations stay blank until the user adds them.
    renderEndpointNote(wire,"from",a,b,isWireSelected);
    renderEndpointNote(wire,"to",b,a,isWireSelected);
  }

  function normalizeBoardType(value) {
    return ["perf","strip","breadboard","breadboardRails"].includes(value) ? value : "perf";
  }

  function normalizeBoard(board) {
    return {
      id:String(board && board.id || uid("board")),
      type:normalizeBoardType(board && board.type),
      x:snap(Number(board && board.x) || 300),
      y:snap(Number(board && board.y) || 300),
      holesX:clamp(Math.round(Number(board && board.holesX) || 30),2,120),
      holesY:clamp(Math.round(Number(board && board.holesY) || 10),2,80),
      rotation:Number(board && board.rotation) || 0,
      scale:clamp(Number(board && board.scale) || 1,.1,10),
      color:board && typeof board.color === "string" ? board.color : "#d9e4c7",
      holeColor:board && typeof board.holeColor === "string" ? board.holeColor : "#3c4248"
    };
  }

  function getBoard(id) {
    return state.boards.find(board => board.id === id) || null;
  }

  function boardGeometry(board) {
    const pitch = GRID;
    const margin = 20;
    const slot = board.type === "breadboard" || board.type === "breadboardRails" ? 18 : 0;
    const terminalHeight = (board.holesY - 1) * pitch;
    const railsExtra = board.type === "breadboardRails" ? 76 : 0;
    return {
      pitch,
      margin,
      slot,
      railsExtra,
      width:margin * 2 + (board.holesX - 1) * pitch,
      height:margin * 2 + terminalHeight + slot + railsExtra
    };
  }

  function boardHoleY(board,row,g) {
    if (board.type !== "breadboard" && board.type !== "breadboardRails") {
      return g.margin + row * g.pitch;
    }
    const half = Math.ceil(board.holesY / 2);
    const terminalTop = g.margin + (board.type === "breadboardRails" ? 38 : 0);
    return terminalTop + row * g.pitch + (row >= half ? g.slot : 0);
  }

  function boardHoleX(col,g) {
    return g.margin + col * g.pitch;
  }

  function addBoard() {
    const next = normalizeBoard({
      id:uid("board"),
      type:boardType.value,
      holesX:Number(boardHolesX.value),
      holesY:Number(boardHolesY.value),
      x:300 + (state.boards.length % 6) * 30,
      y:300 + (state.boards.length % 6) * 30
    });
    const g = boardGeometry(next);
    next.x = snap(clamp(next.x,0,CANVAS_WIDTH-g.width));
    next.y = snap(clamp(next.y,0,CANVAS_HEIGHT-g.height));
    state.boards.push(next);
    state.selected = { kind:"board", id:next.id };
    setStatus("Board underlay added: " + next.holesX + " × " + next.holesY + " holes.");
    render();
  }

  function selectedBoard() {
    return state.selected && state.selected.kind === "board"
      ? getBoard(state.selected.id)
      : null;
  }

  function renderBoard(board) {
    const g = boardGeometry(board);
    const isSelected = state.selected && state.selected.kind === "board" && state.selected.id === board.id;
    const group = svgEl("g", {
      class:"board-underlay" + (isSelected ? " selected" : ""),
      transform:"translate(" + board.x + " " + board.y + ") translate(" + (g.width/2) + " " + (g.height/2) + ") rotate(" + (Number(board.rotation) || 0) + ") scale(" + clamp(Number(board.scale) || 1,.1,10) + ") translate(" + (-g.width/2) + " " + (-g.height/2) + ")",
      style:"--board-fill:" + board.color + ";--board-hole:" + board.holeColor,
      "data-id":board.id
    });

    const base = svgEl("rect", {
      x:0,y:0,width:g.width,height:g.height,rx:8,class:"board-base"
    });
    group.appendChild(base);

    // Stripboard copper/rail indication sits behind the holes.
    if (board.type === "strip") {
      for (let row=0; row<board.holesY; row+=1) {
        const y=boardHoleY(board,row,g);
        group.appendChild(svgEl("line",{
          x1:g.margin-4,y1:y,x2:g.width-g.margin+4,y2:y,class:"board-strip"
        }));
      }
    }

    // Standard breadboard: show the center trench and the 5-hole terminal groups.
    if (board.type === "breadboard" || board.type === "breadboardRails") {
      const half=Math.ceil(board.holesY/2);
      const before=boardHoleY(board,Math.max(0,half-1),g);
      const after=boardHoleY(board,Math.min(board.holesY-1,half),g);
      const slotY=(before+after)/2;
      group.appendChild(svgEl("rect",{
        x:g.margin-7,
        y:slotY-g.slot/2+2,
        width:g.width-(g.margin-7)*2,
        height:Math.max(8,g.slot-4),
        rx:3,
        class:"board-slot"
      }));

      // Faint connection bars: each breadboard column has connected terminal groups on each side.
      for (let col=0; col<board.holesX; col+=1) {
        const x=boardHoleX(col,g);
        if (half > 1) {
          group.appendChild(svgEl("line",{
            x1:x,y1:boardHoleY(board,0,g),
            x2:x,y2:boardHoleY(board,half-1,g),
            class:"board-strip"
          }));
        }
        if (board.holesY-half > 1) {
          group.appendChild(svgEl("line",{
            x1:x,y1:boardHoleY(board,half,g),
            x2:x,y2:boardHoleY(board,board.holesY-1,g),
            class:"board-strip"
          }));
        }
      }
    }

    // Optional breadboard power rails, two rows at top and two at bottom.
    if (board.type === "breadboardRails") {
      const railYs=[14,26,g.height-26,g.height-14];
      railYs.forEach((y,index) => {
        group.appendChild(svgEl("line",{
          x1:g.margin,y1:y,x2:g.width-g.margin,y2:y,
          class:"board-rail" + (index % 2 === 0 ? " power" : "")
        }));
        for (let col=0; col<board.holesX; col+=1) {
          group.appendChild(svgEl("circle",{
            cx:boardHoleX(col,g),cy:y,r:2.8,class:"board-hole"
          }));
        }
      });
    }

    // Main terminal/perf holes.
    for (let row=0; row<board.holesY; row+=1) {
      const y=boardHoleY(board,row,g);
      for (let col=0; col<board.holesX; col+=1) {
        group.appendChild(svgEl("circle",{
          cx:boardHoleX(col,g),cy:y,r:2.8,class:"board-hole"
        }));
      }
    }

    const label=svgEl("text",{
      x:8,y:g.height-6,class:"board-dim","text-anchor":"start"
    });
    label.textContent=board.holesX + "×" + board.holesY + " @ 2.54 mm • " + Math.round(clamp(Number(board.scale) || 1,.1,10)*100) + "%";
    group.appendChild(label);

    group.addEventListener("pointerdown",e => beginBoardDrag(e,board.id));
    group.addEventListener("click",e => {
      state.selected={ kind:"board",id:board.id };
      setStatus("Board underlay selected.");
      render();
    });

    boardsLayer.appendChild(group);
  }

  function defaultComponentFill(kind) {
    if (kind === "resistor") return "#e7d0a6";
    return "#f4f0e7";
  }

  function updateCanvasAppearance() {
    const s = state.canvasSettings;
    document.documentElement.style.setProperty("--canvas-bg", s.bgColor);
    document.documentElement.style.setProperty("--minor-grid", s.minorGridColor);
    document.documentElement.style.setProperty("--major-grid", s.majorGridColor);
    document.documentElement.style.setProperty("--pin-font-size", s.pinFontSize + "px");
    canvas.style.width = (CANVAS_WIDTH * s.zoom) + "px";
    canvas.style.height = (CANVAS_HEIGHT * s.zoom) + "px";

    canvasBgColor.value = s.bgColor;
    minorGridColor.value = s.minorGridColor;
    majorGridColor.value = s.majorGridColor;
    pinFontSize.value = String(s.pinFontSize);
    pinFontSizeOut.textContent = s.pinFontSize + " px";
    zoomRange.value = String(Math.round(s.zoom * 100));
    zoomOut.textContent = Math.round(s.zoom * 100) + "%";
  }

  function selectedWire() {
    return state.selected && (state.selected.kind === "wire" || state.selected.kind === "wireNote")
      ? state.wires.find(w => w.id === state.selected.id) || null
      : null;
  }

  function selectedWireNote() {
    if (!state.selected || state.selected.kind !== "wireNote") return null;
    const wire = state.wires.find(w => w.id === state.selected.id) || null;
    if (!wire) return null;
    const end = state.selected.end === "to" ? "to" : "from";
    return { wire, end, note:ensureWireNotes(wire)[end] };
  }

  function selectedComponent() {
    return state.selected && state.selected.kind === "component"
      ? getComponent(state.selected.id)
      : null;
  }

  function updateInspector() {
    const comp = selectedComponent();
    const wire = selectedWire();
    const wireNote = selectedWireNote();
    const board = selectedBoard();

    boardTools.hidden = !board;
    componentTools.hidden = !comp;
    wireTools.hidden = !wire;
    wireNoteTools.hidden = !wireNote;

    if (board) {
      const g=boardGeometry(board);
      const boardScaleValue=clamp(Number(board.scale) || 1,.1,10);
      selectionKind.textContent="Board";
      selectionName.textContent=board.holesX + " × " + board.holesY + " holes • " +
        Math.round(boardScaleValue*100) + "%";
      selectedBoardType.value=board.type;
      selectedBoardHolesX.value=String(board.holesX);
      selectedBoardHolesY.value=String(board.holesY);
      boardScale.value=String(Math.round(boardScaleValue*100));
      boardColor.value=board.color;
      boardHoleColor.value=board.holeColor;
    } else if (comp) {
      const def = components[comp.type];
      selectionKind.textContent = "Component";
      selectionName.textContent = (def ? def.title : comp.type) + (comp.value ? " — " + comp.value : "");
      componentColor.value = comp.fillColor || defaultComponentFill(def && def.kind);
      componentTextColor.value = comp.textColor || "#191d20";
      componentScale.value = String(Math.round(clamp(Number(comp.scale) || 1,.1,10)*100));
      componentFontSize.value = String(Number(comp.fontSize) || 12);
      componentFontSizeOut.textContent = (Number(comp.fontSize) || 12) + " px";
    } else if (wireNote) {
      selectionKind.textContent = "Wire note";
      selectionName.textContent = (wireNote.end === "from" ? "Start: " : "End: ") +
        describePin(wireNote.end === "from" ? wireNote.wire.from : wireNote.wire.to);
      wireNetType.value = wireNote.wire.net;
      wireColor.value = wireNote.wire.color || NET_COLORS[wireNote.wire.net] || NET_COLORS.OTHER;
      wireWidth.value = String(clamp(Number(wireNote.wire.width) || 4,1,12));
      wireWidthOut.textContent = wireWidth.value + " px";
      wireNoteText.value = wireNote.note.text;
      wireNoteColor.value = wireNote.note.color;
      wireNoteFontSize.value = String(wireNote.note.fontSize);
      wireNoteFontSizeOut.textContent = wireNote.note.fontSize + " px";
    } else if (wire) {
      selectionKind.textContent = "Wire";
      selectionName.textContent = describePin(wire.from) + " → " + describePin(wire.to);
      wireNetType.value = wire.net;
      wireColor.value = wire.color || NET_COLORS[wire.net] || NET_COLORS.OTHER;
      wireWidth.value = String(clamp(Number(wire.width) || 4, 1, 12));
      wireWidthOut.textContent = wireWidth.value + " px";
    } else {
      selectionKind.textContent = "Canvas";
      selectionName.textContent = "Nothing selected";
    }
  }

  function render() {
    updateCanvasAppearance();
    boardsLayer.replaceChildren();
    wiresLayer.replaceChildren();
    componentsLayer.replaceChildren();
    state.boards.forEach(renderBoard);
    state.wires.forEach(renderWire);
    state.components.forEach(renderComponent);
    updateInspector();
  }

  function describePin(ref) {
    const comp = getComponent(ref.compId);
    const pinDef = getPinDef(comp, ref.pinId);
    if (!comp || !pinDef || !components[comp.type]) return "unknown pin";
    return components[comp.type].title + " / " + connectionLabel(pinDef, comp);
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
        net,
        color:null,
        width:4,
        notes:blankWireNotes()
      };
      state.wires.push(wire);
      state.selected = { kind:"wire", id:wire.id };
      setWarning(safetyWarning(wire.from, wire.to, net));
      setStatus(net + " wire: " + describePin(wire.from) + " → " + describePin(wire.to));
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
    if (!matrix) return { x:0,y:0 };
    return point.matrixTransform(matrix.inverse());
  }

  function beginDrag(e, compId) {
    if (e.button !== undefined && e.button !== 0) return;
    if (e.target.classList.contains("pin")) return;

    const comp = getComponent(compId);
    if (!comp) return;

    const p = clientToSvg(e);
    state.drag = {
      kind:"component",
      pointerId:e.pointerId,
      compId,
      dx:p.x-comp.x,
      dy:p.y-comp.y,
      moved:false
    };
    state.selected = { kind:"component", id:compId };
    updateInspector();
    canvas.setPointerCapture(e.pointerId);
    e.preventDefault();
  }

  function beginBoardDrag(e,boardId) {
    if (e.button !== undefined && e.button !== 0) return;
    const board=getBoard(boardId);
    if (!board) return;
    const p=clientToSvg(e);
    state.drag={
      kind:"board",
      pointerId:e.pointerId,
      boardId,
      dx:p.x-board.x,
      dy:p.y-board.y,
      moved:false
    };
    state.selected={ kind:"board",id:boardId };
    updateInspector();
    canvas.setPointerCapture(e.pointerId);
    e.preventDefault();
  }

  canvas.addEventListener("pointermove", e => {
    if (!state.drag || e.pointerId !== state.drag.pointerId) return;
    const p=clientToSvg(e);

    if (state.drag.kind === "board") {
      const board=getBoard(state.drag.boardId);
      if (!board) return;
      const g=boardGeometry(board);
      const nextX=snap(clamp(p.x-state.drag.dx,0,CANVAS_WIDTH-g.width));
      const nextY=snap(clamp(p.y-state.drag.dy,0,CANVAS_HEIGHT-g.height));
      if (nextX !== board.x || nextY !== board.y) state.drag.moved=true;
      board.x=nextX;
      board.y=nextY;
      render();
      return;
    }

    const comp = getComponent(state.drag.compId);
    if (!comp || !components[comp.type]) return;
    const def = components[comp.type];
    const nextX = snap(clamp(p.x-state.drag.dx,0,CANVAS_WIDTH-def.width));
    const nextY = snap(clamp(p.y-state.drag.dy,0,CANVAS_HEIGHT-def.height));
    if (nextX !== comp.x || nextY !== comp.y) state.drag.moved = true;
    comp.x = nextX;
    comp.y = nextY;
    render();
  });

  canvas.addEventListener("pointerup", e => {
    if (!state.drag || e.pointerId !== state.drag.pointerId) return;
    const moved = state.drag.moved;
    const dragKind=state.drag.kind;
    try { canvas.releasePointerCapture(e.pointerId); } catch (_) {}
    state.drag = null;
    state.suppressCanvasClick = true;
    setStatus(dragKind === "board"
      ? (moved ? "Board underlay moved." : "Board underlay selected.")
      : (moved ? "Component moved." : "Component selected."));
    updateInspector();
  });

  canvas.addEventListener("click", e => {
    if (state.suppressCanvasClick) {
      state.suppressCanvasClick = false;
      return;
    }
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

    if (state.selected.kind === "board") {
      state.boards=state.boards.filter(board => board.id !== state.selected.id);
      state.selected=null;
    } else if (state.selected.kind === "component") {
      const id = state.selected.id;
      state.components = state.components.filter(c => c.id !== id);
      state.wires = state.wires.filter(w => w.from.compId !== id && w.to.compId !== id);
      state.selected = null;
    } else if (state.selected.kind === "wireNote") {
      const wire = state.wires.find(w => w.id === state.selected.id);
      if (wire) ensureWireNotes(wire)[state.selected.end === "to" ? "to" : "from"].text = "";
      state.selected = wire ? { kind:"wire", id:wire.id } : null;
    } else {
      state.wires = state.wires.filter(w => w.id !== state.selected.id);
      state.selected = null;
    }


    state.pendingPin = null;
    setStatus("Deleted.");
    render();
  }

  function customDefinitionsUsedByProject() {
    const used = new Set(state.components.map(c => c.type));
    return Array.from(used)
      .filter(id => state.customIds.has(id) && components[id])
      .map(id => ({ id, definition:components[id] }));
  }

  function saveProject() {
    const data = {
      format:"BloomCircuit",
      version:4,
      projectName:projectName.value.trim() || "BloomCircuit",
      gridPx:GRID,
      mmPerPx:MM_PER_PX,
      componentDefinitions:customDefinitionsUsedByProject(),
      canvasSettings:{ ...state.canvasSettings },
      boards:state.boards,
      components:state.components,
      wires:state.wires
    };
    download(cleanFileName(data.projectName)+".json",JSON.stringify(data,null,2),"application/json");
    setStatus("Project JSON saved.");
  }

  function validateLoaded(data) {
    if (!data || !Array.isArray(data.components) || !Array.isArray(data.wires)) {
      throw new Error("Not a BloomCircuit project.");
    }

    if (Array.isArray(data.componentDefinitions)) {
      const pack = { format:"BloomCircuitComponentPack",version:1,components:data.componentDefinitions };
      const count = library.registerPack(pack,true);
      data.componentDefinitions.forEach(item => state.customIds.add(item.id));
      if (count) {
        saveCustomLibraryLocal();
        rebuildLibraryUI();
      }
    }

    const goodBoards=(Array.isArray(data.boards) ? data.boards : [])
      .filter(board => board && typeof board.id === "string")
      .map(board => {
        const normalized=normalizeBoard(board);
        const g=boardGeometry(normalized);
        normalized.x=snap(clamp(normalized.x,0,CANVAS_WIDTH-g.width));
        normalized.y=snap(clamp(normalized.y,0,CANVAS_HEIGHT-g.height));
        return normalized;
      });

    const goodComponents = data.components.filter(c =>
      c && typeof c.id === "string" && components[c.type] &&
      Number.isFinite(Number(c.x)) && Number.isFinite(Number(c.y))
    ).map(c => ({
      id:c.id,
      type:c.type,
      x:snap(Number(c.x)),
      y:snap(Number(c.y)),
      rotation:Number(c.rotation) || 0,
      scale:clamp(Number(c.scale) || 1,.1,10),
      value:typeof c.value === "string" ? c.value : "",
      fillColor:typeof c.fillColor === "string" ? c.fillColor : null,
      textColor:typeof c.textColor === "string" ? c.textColor : null,
      fontSize:clamp(Number(c.fontSize) || 12,7,28)
    }));

    const validIds = new Set(goodComponents.map(c => c.id));
    const goodWires = data.wires.filter(w =>
      w && typeof w.id === "string" &&
      w.from && w.to &&
      validIds.has(w.from.compId) && validIds.has(w.to.compId) &&
      ["5V","3V3","GND","DATA","OTHER"].includes(w.net)
    ).map(w => {
      const normalizeNote = raw => ({
        text:raw && typeof raw.text === "string" ? raw.text : "",
        color:raw && typeof raw.color === "string" ? raw.color : "#24282c",
        fontSize:clamp(raw && Number(raw.fontSize) || 10,6,30)
      });
      return {
        ...w,
        color:typeof w.color === "string" ? w.color : null,
        width:clamp(Number(w.width) || 4,1,12),
        notes:{
          from:normalizeNote(w.notes && w.notes.from),
          to:normalizeNote(w.notes && w.notes.to)
        }
      };
    });

    const rawCanvas = data.canvasSettings || {};
    const canvasSettings = {
      bgColor:typeof rawCanvas.bgColor === "string" ? rawCanvas.bgColor : CANVAS_DEFAULTS.bgColor,
      minorGridColor:typeof rawCanvas.minorGridColor === "string" ? rawCanvas.minorGridColor : CANVAS_DEFAULTS.minorGridColor,
      majorGridColor:typeof rawCanvas.majorGridColor === "string" ? rawCanvas.majorGridColor : CANVAS_DEFAULTS.majorGridColor,
      pinFontSize:clamp(Number(rawCanvas.pinFontSize) || CANVAS_DEFAULTS.pinFontSize,5,18),
      zoom:clamp(Number(rawCanvas.zoom) || CANVAS_DEFAULTS.zoom,.25,2)
    };

    return { boards:goodBoards,components:goodComponents,wires:goodWires,canvasSettings };
  }

  async function loadProject(file) {
    try {
      const data = JSON.parse(await file.text());
      const checked = validateLoaded(data);
      state.boards = checked.boards;
      state.components = checked.components;
      state.wires = checked.wires;
      state.canvasSettings = checked.canvasSettings;
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
    clone.querySelectorAll(".wire-note-handle,.wire-note-plus").forEach(el => el.remove());
    clone.setAttribute("xmlns",NS);
    clone.setAttribute("width",(CANVAS_WIDTH*MM_PER_PX).toFixed(2)+"mm");
    clone.setAttribute("height",(CANVAS_HEIGHT*MM_PER_PX).toFixed(2)+"mm");
    clone.setAttribute("viewBox","0 0 " + CANVAS_WIDTH + " " + CANVAS_HEIGHT);

    const style = document.createElementNS(NS,"style");
    const monochrome = etchMode.checked;
    style.textContent =
      (monochrome
        ? ".component-body,.resistor-body,.led-lens{fill:#fff!important;stroke:#000;stroke-width:2}.component-title,.component-subtitle,.pin-label,.wire-note{fill:#000!important}.wire{stroke:#000!important}"
        : ".component-body{fill:var(--component-fill,#f4f0e7);stroke:#000;stroke-width:2}.resistor-body{fill:var(--component-fill,#e7d0a6)}.led-lens{fill:#f3f7ff;stroke:#000;stroke-width:2}.component-title,.component-subtitle,.pin-label{fill:var(--component-text,#191d20)}") +
      ".component-title{font-weight:700;font-size:var(--component-font-size,12px);text-anchor:middle}" +
      ".component-subtitle{font-size:var(--component-subtitle-size,9px)}" +
      ".pin-label{font-size:" + state.canvasSettings.pinFontSize + "px}" +
      ".pin{fill:#fff;stroke:#000;stroke-width:1.3}" +
      ".bus-line,.cap-plate{stroke:#000;fill:none}" +
      ".wire{fill:none;stroke-linejoin:round;stroke-linecap:round}" +
      ".wire-note{font-weight:600;paint-order:stroke;stroke:#fff;stroke-width:3}" +
      ".board-base{fill:var(--board-fill,#d9e4c7);stroke:#2d3338;stroke-width:2}" +
      ".board-hole{fill:var(--board-hole,#3c4248)}" +
      ".board-slot{fill:#fff;stroke:#7b8288;stroke-width:1.5}" +
      ".board-strip{fill:none;stroke:#8b6f48;stroke-width:5;stroke-linecap:round;opacity:.42}" +
      ".board-rail{fill:none;stroke:#466e96;stroke-width:4;stroke-linecap:round;opacity:.55}" +
      ".board-rail.power{stroke:#b94646}" +
      ".board-dim{fill:#4b535a;font-size:9px}" +
      (monochrome
        ? ".wire-note{fill:#000!important}.board-base{fill:#fff!important;stroke:#000}.board-hole{fill:#000!important}.board-slot{fill:#fff;stroke:#000}.board-strip,.board-rail{stroke:#000!important}"
        : "");

    let defs = clone.querySelector("defs");
    if (!defs) {
      defs = document.createElementNS(NS,"defs");
      clone.insertBefore(defs,clone.firstChild);
    }
    defs.appendChild(style);

    const xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + new XMLSerializer().serializeToString(clone);
    download(cleanFileName(projectName.value)+(monochrome?"_ETCH":"")+".svg",xml,"image/svg+xml");
    setStatus("SVG exported at 10 px = 2.54 mm.");
  }

  function addTemplateWire(fromComp, fromPin, toComp, toPin, net) {
    state.wires.push({
      id:uid("wire"),
      from:{ compId:fromComp.id,pinId:fromPin },
      to:{ compId:toComp.id,pinId:toPin },
      net,
      color:null,
      width:4,
      notes:blankWireNotes()
    });
  }

  function loadHappyJarz() {
    state.boards = [];
    state.boards = [];
    state.boards = [];
    state.components = [];
    state.wires = [];
    state.canvasSettings = { ...CANVAS_DEFAULTS };
    state.selected = null;
    state.pendingPin = null;

    const pi = makeComponent("pi40",20,130);
    const bus5 = makeComponent("bus5",340,45);
    const busg = makeComponent("busg",340,605);
    const chip = makeComponent("ahct125",400,185);
    const resistor = makeComponent("resistor",620,265,{value:"1K"});
    const led1 = makeComponent("apa106",790,180,{value:"LED #1"});
    const led2 = makeComponent("apa106",1010,180,{value:"LED #2"});
    const capChip = makeComponent("capacitor",500,470,{value:"104"});
    const cap1 = makeComponent("capacitor",820,430,{value:"104"});
    const cap2 = makeComponent("capacitor",1040,430,{value:"104"});

    state.components.push(pi,bus5,busg,chip,resistor,led1,led2,capChip,cap1,cap2);

    addTemplateWire(pi,"p02",bus5,"t1","5V");
    addTemplateWire(pi,"p06",busg,"t1","GND");
    addTemplateWire(pi,"p19",chip,"p2","DATA");

    addTemplateWire(chip,"p14",bus5,"t2","5V");
    addTemplateWire(chip,"p7",busg,"t2","GND");
    addTemplateWire(chip,"p1",busg,"t3","GND");

    addTemplateWire(chip,"p3",resistor,"a","DATA");
    addTemplateWire(resistor,"b",led1,"din","DATA");
    addTemplateWire(led1,"dout",led2,"din","DATA");

    addTemplateWire(led1,"vdd",bus5,"t3","5V");
    addTemplateWire(led1,"gnd",busg,"t4","GND");
    addTemplateWire(led2,"vdd",bus5,"t4","5V");
    addTemplateWire(led2,"gnd",busg,"t5","GND");

    addTemplateWire(capChip,"a",bus5,"t5","5V");
    addTemplateWire(capChip,"b",busg,"t6","GND");
    addTemplateWire(cap1,"a",bus5,"t6","5V");
    addTemplateWire(cap1,"b",busg,"t7","GND");
    addTemplateWire(cap2,"a",bus5,"t7","5V");
    addTemplateWire(cap2,"b",busg,"t8","GND");

    addTemplateWire(chip,"p4",bus5,"t8","5V");
    addTemplateWire(chip,"p10",bus5,"t9","5V");
    addTemplateWire(chip,"p13",bus5,"t10","5V");
    addTemplateWire(chip,"p5",busg,"t9","GND");
    addTemplateWire(chip,"p9",busg,"t10","GND");
    addTemplateWire(chip,"p12",busg,"t11","GND");

    projectName.value = "Happy Jarz Circuit";
    setWarning("");
    setStatus("Happy Jarz starter circuit loaded.");
    render();
  }

  function componentSearchText(id, def) {
    return [id,def.title,def.palette,def.category,def.subtitle,...(def.keywords||[])].join(" ").toLowerCase();
  }

  function rebuildCategoryFilter() {
    const current = categoryFilter.value || "ALL";
    const categories = Array.from(new Set(Object.values(components).map(def => def.category || "Other"))).sort();
    categoryFilter.replaceChildren();
    const all = document.createElement("option");
    all.value = "ALL";
    all.textContent = "All categories";
    categoryFilter.appendChild(all);
    categories.forEach(category => {
      const opt = document.createElement("option");
      opt.value = category;
      opt.textContent = category;
      categoryFilter.appendChild(opt);
    });
    categoryFilter.value = categories.includes(current) ? current : "ALL";
  }

  function buildPalette() {
    const query = componentSearch.value.trim().toLowerCase();
    const category = categoryFilter.value || "ALL";
    const rows = Object.entries(components)
      .filter(([id,def]) => category === "ALL" || def.category === category)
      .filter(([id,def]) => !query || componentSearchText(id,def).includes(query))
      .sort((a,b) => {
        const ca = a[1].category || "Other";
        const cb = b[1].category || "Other";
        return ca.localeCompare(cb) || a[1].palette.localeCompare(b[1].palette);
      });

    palette.replaceChildren();
    paletteEmpty.hidden = rows.length !== 0;

    const groups = new Map();
    rows.forEach(row => {
      const categoryName = row[1].category || "Other";
      if (!groups.has(categoryName)) groups.set(categoryName,[]);
      groups.get(categoryName).push(row);
    });

    groups.forEach((items,categoryName) => {
      const group = document.createElement("div");
      group.className = "palette-group";
      const heading = document.createElement("h3");
      heading.textContent = categoryName;
      group.appendChild(heading);

      items.forEach(([type,def]) => {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = "+ " + def.palette;
        button.title = def.subtitle || def.title;
        button.addEventListener("click",() => addComponent(type));
        group.appendChild(button);
      });

      palette.appendChild(group);
    });

    libraryCount.textContent = String(Object.keys(components).length);
  }

  function rebuildLibraryUI() {
    rebuildCategoryFilter();
    buildPalette();
  }

  function customMakerDimensions() {
    const holesX=clamp(Math.round(Number(customWidth.value) || 16),2,80);
    const holesY=clamp(Math.round(Number(customHeight.value) || 10),2,60);
    return {
      holesX,
      holesY,
      width:(holesX-1)*GRID,
      height:(holesY-1)*GRID
    };
  }

  function inferPinSide(x,y,width,height) {
    const choices=[
      ["left",x],
      ["right",Math.abs(width-x)],
      ["top",y],
      ["bottom",Math.abs(height-y)]
    ];
    choices.sort((a,b)=>a[1]-b[1]);
    return choices[0][0];
  }

  function resetCustomMaker() {
    customMaker.pins=[];
    customMaker.selectedIndex=-1;
    customMaker.dragIndex=-1;
    customMaker.imageData="";
    customImageInput.value="";
    customWidth.value="16";
    customHeight.value="10";
    renderCustomMaker();
  }

  function selectedCustomPin() {
    return customMaker.selectedIndex >= 0 && customMaker.selectedIndex < customMaker.pins.length
      ? customMaker.pins[customMaker.selectedIndex]
      : null;
  }

  function renderCustomPinEditor() {
    const pin=selectedCustomPin();
    customPinEmpty.hidden=!!pin;
    customPinEditor.hidden=!pin;

    if (pin) {
      const d=customMakerDimensions();
      customPinId.value=pin.id;
      customPinLabel.value=pin.name;
      customPinRole.value=pin.role;
      customPinX.max=String(d.holesX-1);
      customPinY.max=String(d.holesY-1);
      customPinX.value=String(Math.round(pin.x/GRID));
      customPinY.value=String(Math.round(pin.y/GRID));
    }

    customPinList.replaceChildren();
    customMaker.pins.forEach((pin,index)=>{
      const button=document.createElement("button");
      button.type="button";
      button.className=index===customMaker.selectedIndex ? "active" : "";
      button.textContent=(index+1)+". "+pin.name+" ["+Math.round(pin.x/GRID)+","+Math.round(pin.y/GRID)+"]";
      button.addEventListener("click",()=>{
        customMaker.selectedIndex=index;
        renderCustomMaker();
      });
      customPinList.appendChild(button);
    });
  }

  function renderCustomMaker() {
    const d=customMakerDimensions();
    customMakerSize.textContent=d.holesX+" × "+d.holesY;
    customFootprintPreview.setAttribute("viewBox","0 0 "+Math.max(10,d.width)+" "+Math.max(10,d.height));
    customMakerGridBg.setAttribute("width",String(Math.max(10,d.width)));
    customMakerGridBg.setAttribute("height",String(Math.max(10,d.height)));
    customFootprintImage.setAttribute("width",String(Math.max(10,d.width)));
    customFootprintImage.setAttribute("height",String(Math.max(10,d.height)));

    if (customMaker.imageData) {
      customFootprintImage.setAttribute("href",customMaker.imageData);
      customFootprintImage.removeAttribute("visibility");
    } else {
      customFootprintImage.removeAttribute("href");
      customFootprintImage.setAttribute("visibility","hidden");
    }

    customMaker.pins.forEach(pin=>{
      pin.x=clamp(snap(pin.x),0,d.width);
      pin.y=clamp(snap(pin.y),0,d.height);
      pin.side=inferPinSide(pin.x,pin.y,d.width,d.height);
    });

    customFootprintPins.replaceChildren();
    customMaker.pins.forEach((pin,index)=>{
      const g=svgEl("g",{"data-index":index});
      const circle=svgEl("circle",{
        cx:pin.x,cy:pin.y,r:4.2,
        class:"maker-pin"+(index===customMaker.selectedIndex ? " selected" : "")
      });
      const label=svgEl("text",{
        x:pin.x+6,y:pin.y-5,class:"maker-pin-label","text-anchor":"start"
      });
      label.textContent=pin.name;

      circle.addEventListener("pointerdown",e=>{
        e.stopPropagation();
        customMaker.selectedIndex=index;
        customMaker.dragIndex=index;
        customFootprintPreview.setPointerCapture(e.pointerId);
        renderCustomPinEditor();
      });
      circle.addEventListener("click",e=>{
        e.stopPropagation();
        customMaker.selectedIndex=index;
        renderCustomMaker();
      });

      g.appendChild(circle);
      g.appendChild(label);
      customFootprintPins.appendChild(g);
    });

    renderCustomPinEditor();
  }

  function customPreviewPoint(e) {
    const point=customFootprintPreview.createSVGPoint();
    point.x=e.clientX;
    point.y=e.clientY;
    const matrix=customFootprintPreview.getScreenCTM();
    return matrix ? point.matrixTransform(matrix.inverse()) : {x:0,y:0};
  }

  function addCustomPinAt(x,y) {
    const d=customMakerDimensions();
    x=clamp(snap(x),0,d.width);
    y=clamp(snap(y),0,d.height);
    const number=customMaker.pins.length+1;
    const pin={
      id:"p"+number,
      name:"P"+number,
      role:"passive",
      x,y,
      side:inferPinSide(x,y,d.width,d.height)
    };
    customMaker.pins.push(pin);
    customMaker.selectedIndex=customMaker.pins.length-1;
    renderCustomMaker();
  }

  async function imageFileToEmbeddedData(file) {
    return await new Promise((resolve,reject)=>{
      const reader=new FileReader();
      reader.onerror=()=>reject(new Error("Could not read image."));
      reader.onload=()=>{
        const img=new Image();
        img.onerror=()=>reject(new Error("Could not decode image."));
        img.onload=()=>{
          const max=900;
          const scale=Math.min(1,max/Math.max(img.width,img.height));
          const canvas=document.createElement("canvas");
          canvas.width=Math.max(1,Math.round(img.width*scale));
          canvas.height=Math.max(1,Math.round(img.height*scale));
          const ctx=canvas.getContext("2d");
          ctx.drawImage(img,0,0,canvas.width,canvas.height);
          resolve(canvas.toDataURL("image/webp",0.86));
        };
        img.src=reader.result;
      };
      reader.readAsDataURL(file);
    });
  }

  function createCustomComponentFromForm() {
    const id = customId.value.trim();
    const d=customMakerDimensions();
    if (!customMaker.pins.length) throw new Error("Place at least one pin on the footprint grid.");

    const ids=new Set();
    customMaker.pins.forEach((pin,index)=>{
      const pinId=String(pin.id || "p"+(index+1)).trim();
      if (!pinId) throw new Error("Every pin needs an ID.");
      if (ids.has(pinId)) throw new Error("Pin IDs must be unique. Duplicate: "+pinId);
      ids.add(pinId);
    });

    const definition = {
      title:customTitle.value.trim() || id,
      palette:customTitle.value.trim() || id,
      category:customCategory.value.trim() || "Custom",
      kind:customKind.value,
      width:d.width,
      height:d.height,
      subtitle:customSubtitle.value.trim(),
      keywords:["custom","breadboard","2.54mm"],
      imageData:customMaker.imageData,
      pins:customMaker.pins.map((pin,index)=>({
        id:String(pin.id || "p"+(index+1)).trim(),
        name:String(pin.name || pin.id || "P"+(index+1)).trim(),
        role:pin.role || "passive",
        x:clamp(snap(pin.x),0,d.width),
        y:clamp(snap(pin.y),0,d.height),
        side:inferPinSide(pin.x,pin.y,d.width,d.height)
      }))
    };

    customPins.value=definition.pins.map(pin=>
      [pin.id,pin.name,pin.role,pin.x/GRID,pin.y/GRID].join(" | ")
    ).join("\n");

    library.registerComponent(id,definition,true);
    state.customIds.add(id);
    saveCustomLibraryLocal();
    rebuildLibraryUI();
    return id;
  }

  async function importComponentPack(file) {
    try {
      const pack = JSON.parse(await file.text());
      const count = library.registerPack(pack,true);
      (pack.components || []).forEach(item => state.customIds.add(item.id));
      saveCustomLibraryLocal();
      rebuildLibraryUI();
      setWarning("");
      setStatus("Imported " + count + " component" + (count===1?"":"s") + ".");
    } catch (err) {
      setWarning("Component pack import failed: " + err.message);
    }
  }

  function exportComponentPack() {
    const ids = Array.from(state.customIds).filter(id => components[id]);
    const pack = library.exportPack(ids.length ? ids : Object.keys(components));
    pack.name = ids.length ? "BloomCircuit custom components" : "BloomCircuit full component library";
    download(cleanFileName(pack.name)+".json",JSON.stringify(pack,null,2),"application/json");
    setStatus("Component pack exported (" + pack.components.length + " parts).");
  }

  function updateSelectedBoardFromControls() {
    const board=selectedBoard();
    if (!board) return;
    board.type=normalizeBoardType(selectedBoardType.value);
    board.holesX=clamp(Math.round(Number(selectedBoardHolesX.value) || board.holesX),2,120);
    board.holesY=clamp(Math.round(Number(selectedBoardHolesY.value) || board.holesY),2,80);
    const g=boardGeometry(board);
    board.x=snap(clamp(board.x,0,CANVAS_WIDTH-g.width));
    board.y=snap(clamp(board.y,0,CANVAS_HEIGHT-g.height));
    render();
  }

  document.getElementById("addBoardBtn").addEventListener("click",addBoard);
  document.getElementById("boardRotateLeftBtn").addEventListener("click",() => {
    const board=selectedBoard();
    if (!board) return;
    board.rotation=(((Number(board.rotation)||0)-90)%360+360)%360;
    render();
  });
  document.getElementById("boardRotateRightBtn").addEventListener("click",() => {
    const board=selectedBoard();
    if (!board) return;
    board.rotation=(((Number(board.rotation)||0)+90)%360+360)%360;
    render();
  });
  function setBoardScalePercent(value) {
    const board=selectedBoard();
    if (!board) return;
    const pct=clamp(Math.round(Number(value) || 100),10,1000);
    board.scale=pct/100;
    boardScale.value=String(pct);
    render();
  }

  boardScale.addEventListener("input",()=>setBoardScalePercent(boardScale.value));
  document.getElementById("boardScaleDown").addEventListener("click",()=>setBoardScalePercent(Number(boardScale.value)-1));
  document.getElementById("boardScaleUp").addEventListener("click",()=>setBoardScalePercent(Number(boardScale.value)+1));
  selectedBoardType.addEventListener("change",updateSelectedBoardFromControls);
  selectedBoardHolesX.addEventListener("change",updateSelectedBoardFromControls);
  selectedBoardHolesY.addEventListener("change",updateSelectedBoardFromControls);

  boardColor.addEventListener("input",() => {
    const board=selectedBoard();
    if (!board) return;
    board.color=boardColor.value;
    render();
  });

  boardHoleColor.addEventListener("input",() => {
    const board=selectedBoard();
    if (!board) return;
    board.holeColor=boardHoleColor.value;
    render();
  });

  document.getElementById("deleteBoardBtn").addEventListener("click",() => {
    const board=selectedBoard();
    if (!board) return;
    state.boards=state.boards.filter(item => item.id !== board.id);
    state.selected=null;
    setStatus("Board underlay deleted.");
    render();
  });

  function rotateSelected(delta) {
    const comp = selectedComponent();
    if (!comp) return;
    comp.rotation = (((Number(comp.rotation) || 0) + delta) % 360 + 360) % 360;
    setStatus("Rotated to " + comp.rotation + "°.");
    render();
  }

  document.getElementById("rotateLeftBtn").addEventListener("click",() => rotateSelected(-90));
  document.getElementById("rotateRightBtn").addEventListener("click",() => rotateSelected(90));

  componentColor.addEventListener("input",() => {
    const comp = selectedComponent();
    if (!comp) return;
    comp.fillColor = componentColor.value;
    render();
  });

  componentTextColor.addEventListener("input",() => {
    const comp = selectedComponent();
    if (!comp) return;
    comp.textColor = componentTextColor.value;
    render();
  });

  function setComponentScalePercent(value) {
    const comp=selectedComponent();
    if (!comp) return;
    const pct=clamp(Math.round(Number(value) || 100),10,1000);
    comp.scale=pct/100;
    componentScale.value=String(pct);
    render();
  }

  componentScale.addEventListener("input",()=>setComponentScalePercent(componentScale.value));
  document.getElementById("componentScaleDown").addEventListener("click",()=>setComponentScalePercent(Number(componentScale.value)-1));
  document.getElementById("componentScaleUp").addEventListener("click",()=>setComponentScalePercent(Number(componentScale.value)+1));

  componentFontSize.addEventListener("input",() => {
    const comp = selectedComponent();
    if (!comp) return;
    comp.fontSize = clamp(Number(componentFontSize.value) || 12,7,28);
    render();
  });

  document.getElementById("resetComponentStyleBtn").addEventListener("click",() => {
    const comp = selectedComponent();
    if (!comp) return;
    comp.fillColor = null;
    comp.textColor = null;
    comp.fontSize = 12;
    comp.rotation = 0;
    comp.scale = 1;
    setStatus("Component style reset.");
    render();
  });

  wireNetType.addEventListener("change",() => {
    const wire = selectedWire();
    if (!wire) return;
    wire.net = wireNetType.value;
    wire.color = null;
    setStatus("Wire changed to " + wire.net + ".");
    render();
  });

  wireColor.addEventListener("input",() => {
    const wire = selectedWire();
    if (!wire) return;
    wire.color = wireColor.value;
    render();
  });

  wireWidth.addEventListener("input",() => {
    const wire = selectedWire();
    if (!wire) return;
    wire.width = clamp(Number(wireWidth.value) || 4,1,12);
    render();
  });

  wireNoteText.addEventListener("input",() => {
    const selected = selectedWireNote();
    if (!selected) return;
    selected.note.text = wireNoteText.value.slice(0,500);
    render();
  });

  wireNoteColor.addEventListener("input",() => {
    const selected = selectedWireNote();
    if (!selected) return;
    selected.note.color = wireNoteColor.value;
    render();
  });

  wireNoteFontSize.addEventListener("input",() => {
    const selected = selectedWireNote();
    if (!selected) return;
    selected.note.fontSize = clamp(Number(wireNoteFontSize.value) || 10,6,30);
    render();
  });

  document.getElementById("clearWireNoteBtn").addEventListener("click",() => {
    const selected = selectedWireNote();
    if (!selected) return;
    selected.note.text = "";
    state.selected = { kind:"wire", id:selected.wire.id };
    setStatus("Endpoint note cleared.");
    render();
  });

  document.getElementById("resetWireStyleBtn").addEventListener("click",() => {
    const wire = selectedWire();
    if (!wire) return;
    wire.color = null;
    wire.width = 4;
    setStatus("Wire style reset.");
    render();
  });

  canvasBgColor.addEventListener("input",() => {
    state.canvasSettings.bgColor = canvasBgColor.value;
    render();
  });
  minorGridColor.addEventListener("input",() => {
    state.canvasSettings.minorGridColor = minorGridColor.value;
    render();
  });
  majorGridColor.addEventListener("input",() => {
    state.canvasSettings.majorGridColor = majorGridColor.value;
    render();
  });
  pinFontSize.addEventListener("input",() => {
    state.canvasSettings.pinFontSize = clamp(Number(pinFontSize.value) || 8,5,18);
    render();
  });

  document.getElementById("resetCanvasStyleBtn").addEventListener("click",() => {
    const zoom = state.canvasSettings.zoom;
    state.canvasSettings = { ...CANVAS_DEFAULTS, zoom };
    setStatus("Canvas colors reset.");
    render();
  });

  function setZoom(next) {
    state.canvasSettings.zoom = clamp(Number(next) || 1,.25,2);
    updateCanvasAppearance();
  }

  document.getElementById("zoomOutBtn").addEventListener("click",() => setZoom(state.canvasSettings.zoom - .1));
  document.getElementById("zoomInBtn").addEventListener("click",() => setZoom(state.canvasSettings.zoom + .1));
  document.getElementById("zoomResetBtn").addEventListener("click",() => setZoom(1));
  zoomRange.addEventListener("input",() => setZoom(Number(zoomRange.value) / 100));

    componentSearch.addEventListener("input",buildPalette);
  categoryFilter.addEventListener("change",buildPalette);

  document.getElementById("newComponentBtn").addEventListener("click",() => {
    componentFormError.textContent = "";
    resetCustomMaker();
    componentDialog.showModal();
    customId.focus();
  });
  customWidth.addEventListener("input",renderCustomMaker);
  customHeight.addEventListener("input",renderCustomMaker);

  customFootprintPreview.addEventListener("click",e=>{
    if (e.target.classList.contains("maker-pin")) return;
    addCustomPinAt(customPreviewPoint(e).x,customPreviewPoint(e).y);
  });

  customFootprintPreview.addEventListener("pointermove",e=>{
    if (customMaker.dragIndex < 0) return;
    const pin=customMaker.pins[customMaker.dragIndex];
    if (!pin) return;
    const d=customMakerDimensions();
    const p=customPreviewPoint(e);
    pin.x=clamp(snap(p.x),0,d.width);
    pin.y=clamp(snap(p.y),0,d.height);
    renderCustomMaker();
  });

  customFootprintPreview.addEventListener("pointerup",e=>{
    if (customMaker.dragIndex < 0) return;
    try { customFootprintPreview.releasePointerCapture(e.pointerId); } catch (_) {}
    customMaker.dragIndex=-1;
    renderCustomMaker();
  });

  customImageInput.addEventListener("change",async()=>{
    const file=customImageInput.files && customImageInput.files[0];
    if (!file) return;
    try {
      customMaker.imageData=await imageFileToEmbeddedData(file);
      renderCustomMaker();
    } catch (err) {
      componentFormError.textContent=err.message;
    }
  });

  document.getElementById("clearCustomImageBtn").addEventListener("click",()=>{
    customMaker.imageData="";
    customImageInput.value="";
    renderCustomMaker();
  });

  function updateSelectedCustomPinFromEditor() {
    const pin=selectedCustomPin();
    if (!pin) return;
    const d=customMakerDimensions();
    pin.id=customPinId.value.trim() || pin.id;
    pin.name=customPinLabel.value.trim() || pin.id;
    pin.role=customPinRole.value;
    pin.x=clamp(Math.round(Number(customPinX.value)||0)*GRID,0,d.width);
    pin.y=clamp(Math.round(Number(customPinY.value)||0)*GRID,0,d.height);
    pin.side=inferPinSide(pin.x,pin.y,d.width,d.height);
    renderCustomMaker();
  }

  customPinId.addEventListener("change",updateSelectedCustomPinFromEditor);
  customPinLabel.addEventListener("input",updateSelectedCustomPinFromEditor);
  customPinRole.addEventListener("change",updateSelectedCustomPinFromEditor);
  customPinX.addEventListener("change",updateSelectedCustomPinFromEditor);
  customPinY.addEventListener("change",updateSelectedCustomPinFromEditor);

  document.getElementById("deleteCustomPinBtn").addEventListener("click",()=>{
    if (customMaker.selectedIndex < 0) return;
    customMaker.pins.splice(customMaker.selectedIndex,1);
    customMaker.selectedIndex=Math.min(customMaker.selectedIndex,customMaker.pins.length-1);
    renderCustomMaker();
  });

  document.getElementById("closeComponentDialog").addEventListener("click",() => componentDialog.close());
  document.getElementById("cancelComponentBtn").addEventListener("click",() => componentDialog.close());

  componentForm.addEventListener("submit",e => {
    e.preventDefault();
    try {
      const id = createCustomComponentFromForm();
      componentFormError.textContent = "";
      componentDialog.close();
      componentSearch.value = id;
      categoryFilter.value = "ALL";
      buildPalette();
      setStatus("Custom component '" + id + "' added and saved locally.");
    } catch (err) {
      componentFormError.textContent = err.message;
    }
  });

  document.getElementById("importPackBtn").addEventListener("click",() => packInput.click());
  document.getElementById("exportPackBtn").addEventListener("click",exportComponentPack);
  packInput.addEventListener("change",() => {
    const file = packInput.files && packInput.files[0];
    if (file) importComponentPack(file);
    packInput.value = "";
  });

  document.getElementById("happyJarzBtn").addEventListener("click",loadHappyJarz);
  document.getElementById("saveBtn").addEventListener("click",saveProject);
  document.getElementById("loadBtn").addEventListener("click",() => loadInput.click());
  document.getElementById("exportBtn").addEventListener("click",exportSvg);
  document.getElementById("deleteBtn").addEventListener("click",deleteSelected);

  document.getElementById("clearBtn").addEventListener("click",() => {
    if (!window.confirm("Clear the entire BloomCircuit canvas?")) return;
    state.components = [];
    state.wires = [];
    state.canvasSettings = { ...CANVAS_DEFAULTS };
    state.selected = null;
    state.pendingPin = null;
    setWarning("");
    setStatus("Canvas cleared.");
    render();
  });

  loadInput.addEventListener("change",() => {
    const file = loadInput.files && loadInput.files[0];
    if (file) loadProject(file);
    loadInput.value = "";
  });

  etchMode.addEventListener("change",() => {
    document.body.classList.toggle("etch-mode",etchMode.checked);
    setStatus(etchMode.checked ? "Etch view enabled." : "Color wiring view enabled.");
  });

  document.addEventListener("keydown",e => {
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

  loadCustomLibraryLocal();
  rebuildLibraryUI();
  loadHappyJarz();
})();
