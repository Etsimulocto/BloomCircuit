from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.js"
CSS = ROOT / "styles.css"
README = ROOT / "README.md"


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly 1 match, found {count}")
    return text.replace(old, new, 1)


app = APP.read_text(encoding="utf-8")

old = '''  function connectionLabel(pinDef, comp) {
'''
new = '''  function endpointKey(ref) {
    if (!ref || typeof ref !== "object") return "";
    if (ref.compId && ref.pinId) return "component:" + ref.compId + ":" + ref.pinId;
    if (ref.boardId && ref.nodeId) return "board:" + ref.boardId + ":" + ref.nodeId;
    return "";
  }

  function sameEndpoint(a,b) {
    const ak=endpointKey(a);
    return !!ak && ak === endpointKey(b);
  }

  function boardNodeLocal(board,nodeId) {
    if (!board || typeof nodeId !== "string") return null;
    const g=boardGeometry(board);
    let match=nodeId.match(/^h_(\\d+)_(\\d+)$/);
    if (match) {
      const row=Number(match[1]);
      const col=Number(match[2]);
      if (row < 0 || row >= board.holesY || col < 0 || col >= board.holesX) return null;
      return { kind:"hole",row,col,x:boardHoleX(col,g),y:boardHoleY(board,row,g) };
    }
    match=nodeId.match(/^r_(\\d+)_(\\d+)$/);
    if (match && board.type === "breadboardRails") {
      const rail=Number(match[1]);
      const col=Number(match[2]);
      if (rail < 0 || rail > 3 || col < 0 || col >= board.holesX) return null;
      const railYs=[14,26,g.height-26,g.height-14];
      return { kind:"rail",rail,col,x:boardHoleX(col,g),y:railYs[rail] };
    }
    return null;
  }

  function boardElectricalGroup(board,nodeId) {
    const node=boardNodeLocal(board,nodeId);
    if (!node) return "";
    if (node.kind === "rail") return "rail:" + node.rail;
    if (board.type === "perf") return "isolated:" + node.row + ":" + node.col;
    if (board.type === "strip") return "strip:" + node.row;
    const half=Math.ceil(board.holesY/2);
    return "terminal:" + node.col + ":" + (node.row < half ? "top" : "bottom");
  }

  function boardNodeLabel(board,nodeId) {
    const node=boardNodeLocal(board,nodeId);
    if (!node) return "unknown hole";
    if (node.kind === "rail") {
      const names=["TOP +","TOP -","BOTTOM +","BOTTOM -"];
      return names[node.rail] + " " + (node.col+1);
    }
    if (board.type === "breadboard" || board.type === "breadboardRails") {
      const rowLabel=node.row < 26 ? String.fromCharCode(65+node.row) : "R"+(node.row+1);
      return rowLabel + (node.col+1);
    }
    return "R"+(node.row+1)+"C"+(node.col+1);
  }

  function boardGroupLabel(board,nodeId) {
    const node=boardNodeLocal(board,nodeId);
    if (!node) return "";
    if (node.kind === "rail") {
      return ["top + rail","top - rail","bottom + rail","bottom - rail"][node.rail];
    }
    if (board.type === "perf") return "isolated hole";
    if (board.type === "strip") return "connected strip row " + (node.row+1);
    const half=Math.ceil(board.holesY/2);
    const first=node.row < half ? 0 : half;
    const last=node.row < half ? half-1 : board.holesY-1;
    const firstLabel=first < 26 ? String.fromCharCode(65+first) : "R"+(first+1);
    const lastLabel=last < 26 ? String.fromCharCode(65+last) : "R"+(last+1);
    return "connected " + firstLabel + "–" + lastLabel + " column " + (node.col+1);
  }

  function boardNodeWorld(boardId,nodeId) {
    const board=getBoard(boardId);
    const node=boardNodeLocal(board,nodeId);
    if (!board || !node) return null;
    const g=boardGeometry(board);
    const angle=((Number(board.rotation)||0)%360+360)%360;
    const scale=clamp(Number(board.scale)||1,.1,10);
    const cx=g.width/2;
    const cy=g.height/2;
    const rad=angle*Math.PI/180;
    const dx=(node.x-cx)*scale;
    const dy=(node.y-cy)*scale;
    return {
      x:board.x+cx+dx*Math.cos(rad)-dy*Math.sin(rad),
      y:board.y+cy+dx*Math.sin(rad)+dy*Math.cos(rad)
    };
  }

  function endpointWorld(ref) {
    if (ref && ref.compId && ref.pinId) return pinWorld(ref.compId,ref.pinId);
    if (ref && ref.boardId && ref.nodeId) return boardNodeWorld(ref.boardId,ref.nodeId);
    return null;
  }

  function endpointRole(ref) {
    if (!ref || !ref.compId || !ref.pinId) return null;
    const comp=getComponent(ref.compId);
    const pin=getPinDef(comp,ref.pinId);
    return pin && pin.role || null;
  }

  function connectionLabel(pinDef, comp) {
'''
app = replace_once(app, old, new, "endpoint helpers")

old = '''      class: "pin" + (state.pendingPin && state.pendingPin.compId === comp.id && state.pendingPin.pinId === pinDef.id ? " pending" : ""),
'''
new = '''      class: "pin" + (sameEndpoint(state.pendingPin,{compId:comp.id,pinId:pinDef.id}) ? " pending" : ""),
'''
app = replace_once(app, old, new, "component pending pin")

old = '''  function wirePath(a, b) {
    const dx = Math.abs(b.x - a.x);
    if (dx > 50) {
      const mx = snap((a.x + b.x) / 2);
      return "M " + a.x + " " + a.y + " H " + mx + " V " + b.y + " H " + b.x;
    }
    const my = snap((a.y + b.y) / 2);
    return "M " + a.x + " " + a.y + " V " + my + " H " + b.x + " V " + b.y;
  }
'''
new = '''  function wireLaneOffset(wire) {
    const id=String(wire && wire.id || "wire");
    let hash=0;
    for (let i=0;i<id.length;i+=1) hash=((hash*31)+id.charCodeAt(i))>>>0;
    return ((hash % 7)-3)*GRID;
  }

  function wirePath(a,b,wire) {
    const dx=b.x-a.x;
    const dy=b.y-a.y;
    const lane=wireLaneOffset(wire);

    // Give every wire a short escape segment before it enters a routing lane.
    // The staggered lane offset keeps bundles readable instead of stacking them.
    if (Math.abs(dx) >= Math.abs(dy)) {
      const dir=dx >= 0 ? 1 : -1;
      const escape=Math.max(GRID,Math.min(GRID*2,Math.abs(dx)/3 || GRID));
      const ax=a.x+dir*escape;
      const bx=b.x-dir*escape;
      const laneY=snap((a.y+b.y)/2+lane);
      return "M "+a.x+" "+a.y+" H "+ax+" V "+laneY+" H "+bx+" V "+b.y+" H "+b.x;
    }

    const dir=dy >= 0 ? 1 : -1;
    const escape=Math.max(GRID,Math.min(GRID*2,Math.abs(dy)/3 || GRID));
    const ay=a.y+dir*escape;
    const by=b.y-dir*escape;
    const laneX=snap((a.x+b.x)/2+lane);
    return "M "+a.x+" "+a.y+" V "+ay+" H "+laneX+" V "+by+" H "+b.x+" V "+b.y;
  }
'''
app = replace_once(app, old, new, "wire routing lanes")

old = '''  function renderWire(wire) {
    const a = pinWorld(wire.from.compId, wire.from.pinId);
    const b = pinWorld(wire.to.compId, wire.to.pinId);
'''
new = '''  function renderWire(wire) {
    const a = endpointWorld(wire.from);
    const b = endpointWorld(wire.to);
'''
app = replace_once(app, old, new, "wire endpoint world")

old = '''      d: wirePath(a,b),
'''
new = '''      d: wirePath(a,b,wire),
'''
app = replace_once(app, old, new, "wire path call")

old = '''  function selectedBoard() {
    return state.selected && state.selected.kind === "board"
      ? getBoard(state.selected.id)
      : null;
  }

  function renderBoard(board) {
'''
new = '''  function selectedBoard() {
    return state.selected && state.selected.kind === "board"
      ? getBoard(state.selected.id)
      : null;
  }

  function renderBoardNode(group,board,nodeId,x,y) {
    const ref={ boardId:board.id,nodeId };
    const ownGroup=boardElectricalGroup(board,nodeId);
    let pendingGroup="";
    if (state.pendingPin && state.pendingPin.boardId === board.id) {
      pendingGroup=boardElectricalGroup(board,state.pendingPin.nodeId);
    }
    const classes=["board-node"];
    if (sameEndpoint(state.pendingPin,ref)) classes.push("pending");
    else if (pendingGroup && ownGroup === pendingGroup) classes.push("group-pending");

    const node=svgEl("circle",{
      cx:x,cy:y,r:5.5,
      class:classes.join(" "),
      "data-board-id":board.id,
      "data-node-id":nodeId
    });
    const title=svgEl("title");
    title.textContent=boardNodeLabel(board,nodeId)+" • "+boardGroupLabel(board,nodeId);
    node.appendChild(title);
    node.addEventListener("pointerdown",e=>e.stopPropagation());
    node.addEventListener("click",e=>{
      e.stopPropagation();
      handleBoardNodeClick(board.id,nodeId);
    });
    group.appendChild(node);
  }

  function renderBoard(board) {
'''
app = replace_once(app, old, new, "board node renderer")

old = '''          group.appendChild(svgEl("circle",{
            cx:boardHoleX(col,g),cy:y,r:2.8,class:"board-hole"
          }));
'''
new = '''          const x=boardHoleX(col,g);
          group.appendChild(svgEl("circle",{
            cx:x,cy:y,r:2.8,class:"board-hole"
          }));
          renderBoardNode(group,board,"r_"+index+"_"+col,x,y);
'''
app = replace_once(app, old, new, "rail clickable nodes")

old = '''        group.appendChild(svgEl("circle",{
          cx:boardHoleX(col,g),cy:y,r:2.8,class:"board-hole"
        }));
'''
new = '''        const x=boardHoleX(col,g);
        group.appendChild(svgEl("circle",{
          cx:x,cy:y,r:2.8,class:"board-hole"
        }));
        renderBoardNode(group,board,"h_"+row+"_"+col,x,y);
'''
app = replace_once(app, old, new, "terminal clickable nodes")

old = '''  function describePin(ref) {
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
'''
new = '''  function describePin(ref) {
    if (ref && ref.boardId && ref.nodeId) {
      const board=getBoard(ref.boardId);
      if (!board || !boardNodeLocal(board,ref.nodeId)) return "unknown board hole";
      const typeNames={perf:"Perfboard",strip:"Stripboard",breadboard:"Breadboard",breadboardRails:"Breadboard + rails"};
      return (typeNames[board.type] || "Board") + " / " + boardNodeLabel(board,ref.nodeId) + " (" + boardGroupLabel(board,ref.nodeId) + ")";
    }
    const comp = getComponent(ref && ref.compId);
    const pinDef = getPinDef(comp, ref && ref.pinId);
    if (!comp || !pinDef || !components[comp.type]) return "unknown pin";
    return components[comp.type].title + " / " + connectionLabel(pinDef, comp);
  }

  function safetyWarning(from, to, net) {
    const roles = [endpointRole(from),endpointRole(to)];
'''
app = replace_once(app, old, new, "generic endpoint descriptions")

old_start = '''  function handlePinClick(compId, pinId) {
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
'''
new_start = '''  function handleConnectionClick(ref) {
    if (!state.pendingPin) {
      state.pendingPin={ ...ref };
      setWarning("");
      setStatus("Start: " + describePin(ref) + ". Choose destination pin or board hole.");
      render();
      return;
    }

    if (sameEndpoint(state.pendingPin,ref)) {
      state.pendingPin=null;
      setStatus("Wire cancelled.");
      render();
      return;
    }

    const net=netType.value;
    const exists=state.wires.some(w =>
      (sameEndpoint(w.from,state.pendingPin) && sameEndpoint(w.to,ref)) ||
      (sameEndpoint(w.to,state.pendingPin) && sameEndpoint(w.from,ref))
    );

    if (!exists) {
      const wire={
        id:uid("wire"),
        from:{ ...state.pendingPin },
        to:{ ...ref },
        net,
        color:null,
        width:4,
        notes:blankWireNotes()
      };
      state.wires.push(wire);
      state.selected={ kind:"wire",id:wire.id };
      setWarning(safetyWarning(wire.from,wire.to,net));
      setStatus(net + " wire: " + describePin(wire.from) + " → " + describePin(wire.to));
    } else {
      setStatus("Those connection points are already wired together.");
    }

    state.pendingPin=null;
    render();
  }

  function handlePinClick(compId,pinId) {
    handleConnectionClick({ compId,pinId });
  }

  function handleBoardNodeClick(boardId,nodeId) {
    handleConnectionClick({ boardId,nodeId });
  }
'''
app = replace_once(app, old_start, new_start, "generic connection click")

old = '''  function beginBoardDrag(e,boardId) {
    if (e.button !== undefined && e.button !== 0) return;
'''
new = '''  function beginBoardDrag(e,boardId) {
    if (e.button !== undefined && e.button !== 0) return;
    if (e.target.classList && e.target.classList.contains("board-node")) return;
'''
app = replace_once(app, old, new, "board node drag guard")

old = '''    if (state.selected.kind === "board") {
      state.boards=state.boards.filter(board => board.id !== state.selected.id);
      state.selected=null;
'''
new = '''    if (state.selected.kind === "board") {
      const id=state.selected.id;
      state.boards=state.boards.filter(board => board.id !== id);
      state.wires=state.wires.filter(w => w.from.boardId !== id && w.to.boardId !== id);
      state.selected=null;
'''
app = replace_once(app, old, new, "delete selected board wires")

app = replace_once(app, '      version:4,\n', '      version:5,\n', "project version")

old = '''    const validIds = new Set(goodComponents.map(c => c.id));
    const goodWires = data.wires.filter(w =>
      w && typeof w.id === "string" &&
      w.from && w.to &&
      validIds.has(w.from.compId) && validIds.has(w.to.compId) &&
      ["5V","3V3","GND","DATA","OTHER"].includes(w.net)
    ).map(w => {
'''
new = '''    const validIds = new Set(goodComponents.map(c => c.id));
    const boardMap=new Map(goodBoards.map(board => [board.id,board]));
    const validEndpoint=ref => {
      if (!ref || typeof ref !== "object") return false;
      if (ref.compId && ref.pinId) return validIds.has(ref.compId) && typeof ref.pinId === "string";
      if (ref.boardId && ref.nodeId) {
        const board=boardMap.get(ref.boardId);
        return !!board && !!boardNodeLocal(board,ref.nodeId);
      }
      return false;
    };
    const normalizeEndpoint=ref => ref.compId
      ? { compId:String(ref.compId),pinId:String(ref.pinId) }
      : { boardId:String(ref.boardId),nodeId:String(ref.nodeId) };
    const goodWires = data.wires.filter(w =>
      w && typeof w.id === "string" &&
      validEndpoint(w.from) && validEndpoint(w.to) &&
      ["5V","3V3","GND","DATA","OTHER"].includes(w.net)
    ).map(w => {
'''
app = replace_once(app, old, new, "load board wire endpoints")

old = '''      return {
        ...w,
        color:typeof w.color === "string" ? w.color : null,
'''
new = '''      return {
        ...w,
        from:normalizeEndpoint(w.from),
        to:normalizeEndpoint(w.to),
        color:typeof w.color === "string" ? w.color : null,
'''
app = replace_once(app, old, new, "normalize wire endpoints")

old = '''    clone.querySelectorAll(".wire-note-handle,.wire-note-plus").forEach(el => el.remove());
'''
new = '''    clone.querySelectorAll(".wire-note-handle,.wire-note-plus,.board-node").forEach(el => el.remove());
'''
app = replace_once(app, old, new, "remove board hit nodes from SVG")

old = '''  function loadHappyJarz() {
    state.boards = [];
    state.boards = [];
    state.boards = [];
'''
new = '''  function loadHappyJarz() {
    state.boards = [];
'''
app = replace_once(app, old, new, "duplicate board reset")

old = '''  function updateSelectedBoardFromControls() {
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
'''
new = '''  function updateSelectedBoardFromControls() {
    const board=selectedBoard();
    if (!board) return;
    board.type=normalizeBoardType(selectedBoardType.value);
    board.holesX=clamp(Math.round(Number(selectedBoardHolesX.value) || board.holesX),2,120);
    board.holesY=clamp(Math.round(Number(selectedBoardHolesY.value) || board.holesY),2,80);
    const g=boardGeometry(board);
    board.x=snap(clamp(board.x,0,CANVAS_WIDTH-g.width));
    board.y=snap(clamp(board.y,0,CANVAS_HEIGHT-g.height));

    // Resizing or changing board type can remove physical holes/rails.
    state.wires=state.wires.filter(w => {
      if (w.from.boardId === board.id && !boardNodeLocal(board,w.from.nodeId)) return false;
      if (w.to.boardId === board.id && !boardNodeLocal(board,w.to.nodeId)) return false;
      return true;
    });
    if (state.pendingPin && state.pendingPin.boardId === board.id && !boardNodeLocal(board,state.pendingPin.nodeId)) {
      state.pendingPin=null;
    }
    render();
  }
'''
app = replace_once(app, old, new, "prune resized board connections")

old = '''  document.getElementById("deleteBoardBtn").addEventListener("click",() => {
    const board=selectedBoard();
    if (!board) return;
    state.boards=state.boards.filter(item => item.id !== board.id);
    state.selected=null;
'''
new = '''  document.getElementById("deleteBoardBtn").addEventListener("click",() => {
    const board=selectedBoard();
    if (!board) return;
    state.boards=state.boards.filter(item => item.id !== board.id);
    state.wires=state.wires.filter(w => w.from.boardId !== board.id && w.to.boardId !== board.id);
    state.selected=null;
'''
app = replace_once(app, old, new, "delete board button wires")

old = '''    state.components = [];
    state.wires = [];
'''
new = '''    state.boards = [];
    state.components = [];
    state.wires = [];
'''
app = replace_once(app, old, new, "clear boards")

APP.write_text(app, encoding="utf-8")

css = CSS.read_text(encoding="utf-8")
anchor = '''.board-hole {
  fill: var(--board-hole, #3c4248);
  pointer-events: none;
}
'''
insert = anchor + '''
.board-node {
  fill: transparent;
  stroke: transparent;
  stroke-width: 1.5;
  cursor: crosshair;
  pointer-events: all;
}

.board-node:hover {
  fill: rgba(255, 224, 138, .72);
  stroke: #111;
}

.board-node.group-pending {
  fill: rgba(141, 214, 168, .34);
  stroke: rgba(37, 99, 235, .55);
}

.board-node.pending {
  fill: #ffe08a;
  stroke: #111;
  stroke-width: 2.2;
}
'''
css = replace_once(css, anchor, insert, "board node styles")
CSS.write_text(css, encoding="utf-8")

readme = README.read_text(encoding="utf-8")
if "## v0.6 electrical boards" not in readme:
    marker = "## Raspberry Pi offline app\n"
    section = '''## v0.6 electrical boards

Board underlays are now real electrical objects instead of passive background graphics.

- every visible board hole is a clickable connection node
- breadboard terminal groups model the connected holes on each side of the center trench
- breadboard power rails are real connection groups
- stripboard rows are electrically grouped as continuous copper strips
- perfboard holes remain isolated unless the user explicitly wires them
- wires can run component → board hole, board hole → board hole, or board hole → component
- selecting one breadboard hole highlights the other holes in its electrical group
- project JSON v5 preserves board-hole wire endpoints while still loading older component-only projects
- wires now leave endpoints through short escape segments and staggered routing lanes to reduce overlap

This lets BloomCircuit document the physical bench build rather than drawing every connection as a component-to-component abstraction.

'''
    if marker not in readme:
        raise SystemExit("README marker not found")
    readme = readme.replace(marker, section + marker, 1)
README.write_text(readme, encoding="utf-8")

print("BloomCircuit v0.6 electrical-board migration applied.")
