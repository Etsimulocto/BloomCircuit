from pathlib import Path
import re


def sub(text, pattern, replacement, label, flags=0):
    out, n = re.subn(pattern, lambda _m: replacement, text, count=1, flags=flags)
    if n != 1:
        raise SystemExit(f"missing/ambiguous patch target: {label} ({n})")
    return out


app = Path("app.js").read_text()

app = sub(
    app,
    r'  const componentTools = document\.getElementById\("componentTools"\);\n',
    '  const componentTools = document.getElementById("componentTools");\n  const componentTitle = document.getElementById("componentTitle");\n  const componentValue = document.getElementById("componentValue");\n  const componentPinLabels = document.getElementById("componentPinLabels");\n',
    "component inspector controls",
)

app = sub(
    app,
    r'      scale: clamp\(Number\(opts\.scale\) \|\| 1, \.25, 4\),\n      value: opts\.value !== undefined \? opts\.value : \(def\.defaultValue \|\| ""\),',
    '      scale: clamp(Number(opts.scale) || 1, .25, 4),\n      title: opts.title !== undefined ? String(opts.title) : "",\n      value: opts.value !== undefined ? opts.value : (def.defaultValue || ""),\n      pinLabels: opts.pinLabels && typeof opts.pinLabels === "object" ? { ...opts.pinLabels } : {},',
    "component instance metadata",
)

app = sub(
    app,
    r'  function connectionLabel\(pinDef, comp\) \{\n(.*?)\n  \}',
    '''  function connectionLabel(pinDef, comp) {
    const override = comp && comp.pinLabels && typeof comp.pinLabels[pinDef.id] === "string"
      ? comp.pinLabels[pinDef.id].trim()
      : "";
    if (override) return override;
    if (comp.type === "pi40") {
      if ([1,2,4,6,19].includes(pinDef.number)) return pinDef.number + " " + pinDef.name;
      return String(pinDef.number);
    }
    if (pinDef.number) return pinDef.number + " " + pinDef.name;
    return pinDef.name;
  }''',
    "per-instance pin labels",
    re.S,
)

app = sub(
    app,
    r'''    if \(pinDef\.side === "left"\) \{\n      x \+= 9; anchor = "start";\n    \} else if \(pinDef\.side === "right"\) \{\n      x -= 9; anchor = "end";\n    \} else if \(pinDef\.side === "top"\) \{\n      y \+= 14;\n    \} else if \(pinDef\.side === "bottom"\) \{\n      y -= 9;\n    \}\n\n    addText\(group, connectionLabel\(pinDef, comp\), x, y, "pin-label", anchor\);''',
    '''    if (pinDef.side === "left") {
      x -= 9; anchor = "end";
    } else if (pinDef.side === "right") {
      x += 9; anchor = "start";
    } else if (pinDef.side === "top") {
      y -= 9;
    } else if (pinDef.side === "bottom") {
      y += 14;
    }

    const label = addText(group, connectionLabel(pinDef, comp), x, y, "pin-label", anchor);
    const angle = Number(comp.rotation) || 0;
    if (angle) label.setAttribute("transform", "rotate(" + (-angle) + " " + x + " " + y + ")");''',
    "upright external pin labels",
)

app = sub(
    app,
    r'''    const titleY = Math\.max\(8, Math\.min\(def\.kind === "pi40" \? 20 : 18, def\.height \* \.28\)\);\n    addText\(group, def\.title, def\.width / 2, titleY, "component-title"\);\n\n    const detailY = titleY \+ Math\.max\(8, subtitleSize \+ 2\);\n    if \(comp\.value && detailY < def\.height - 3\) \{\n      addText\(group, comp\.value, def\.width / 2, detailY, "component-subtitle"\);\n    \} else if \(def\.subtitle && comp\.type !== "pi40" && detailY < def\.height - 3\) \{\n      addText\(group, def\.subtitle, def\.width / 2, detailY, "component-subtitle"\);\n    \}''',
    '''    const angle = Number(comp.rotation) || 0;
    const titleX = def.width / 2;
    const titleY = -Math.max(8, (Number(comp.fontSize) || 12) * .45);
    const titleText = comp.title && comp.title.trim() ? comp.title.trim() : def.title;
    const titleEl = addText(group, titleText, titleX, titleY, "component-title");
    if (angle) titleEl.setAttribute("transform", "rotate(" + (-angle) + " " + titleX + " " + titleY + ")");

    const detailText = comp.value || (def.subtitle && comp.type !== "pi40" ? def.subtitle : "");
    if (detailText) {
      const detailY = def.height + Math.max(11, subtitleSize + 5);
      const detailEl = addText(group, detailText, titleX, detailY, "component-subtitle");
      if (angle) detailEl.setAttribute("transform", "rotate(" + (-angle) + " " + titleX + " " + detailY + ")");
    }''',
    "external upright title/value",
)

app = sub(
    app,
    r'''      selectionKind\.textContent = "Component";\n      selectionName\.textContent = \(def \? def\.title : comp\.type\) \+ \(comp\.value \? " — " \+ comp\.value : ""\);\n      componentColor\.value = comp\.fillColor \|\| defaultComponentFill\(def && def\.kind\);''',
    '''      selectionKind.textContent = "Component";
      const displayTitle = comp.title && comp.title.trim() ? comp.title.trim() : (def ? def.title : comp.type);
      selectionName.textContent = displayTitle + (comp.value ? " — " + comp.value : "");
      componentTitle.value = comp.title || "";
      componentTitle.placeholder = def ? def.title : comp.type;
      componentValue.value = comp.value || "";
      componentPinLabels.value = Object.entries(comp.pinLabels || {}).map(([id,label]) => id + " = " + label).join("\\n");
      componentColor.value = comp.fillColor || defaultComponentFill(def && def.kind);''',
    "populate component editor",
)

app = sub(
    app,
    r'''      value:typeof c\.value === "string" \? c\.value : "",\n      fillColor:typeof c\.fillColor === "string" \? c\.fillColor : null,''',
    '''      title:typeof c.title === "string" ? c.title : "",
      value:typeof c.value === "string" ? c.value : "",
      pinLabels:c.pinLabels && typeof c.pinLabels === "object" && !Array.isArray(c.pinLabels)
        ? Object.fromEntries(Object.entries(c.pinLabels).filter(([id,label]) => typeof id === "string" && typeof label === "string"))
        : {},
      fillColor:typeof c.fillColor === "string" ? c.fillColor : null,''',
    "load component metadata",
)

app = sub(app, r'version:5,', 'version:6,', 'project format version')

app = sub(
    app,
    r'''  document\.getElementById\("rotateRightBtn"\)\.addEventListener\("click",\(\) => rotateSelected\(90\)\);\n\n  componentColor\.addEventListener''',
    '''  document.getElementById("rotateRightBtn").addEventListener("click",() => rotateSelected(90));

  componentTitle.addEventListener("input",() => {
    const comp = selectedComponent();
    if (!comp) return;
    comp.title = componentTitle.value.slice(0,120);
    render();
  });

  componentValue.addEventListener("input",() => {
    const comp = selectedComponent();
    if (!comp) return;
    comp.value = componentValue.value.slice(0,160);
    render();
  });

  componentPinLabels.addEventListener("input",() => {
    const comp = selectedComponent();
    if (!comp) return;
    const labels = {};
    componentPinLabels.value.split(/\\r?\\n/).forEach(line => {
      const match = line.match(/^\\s*([^=:\\s]+)\\s*(?:=|:)\\s*(.*?)\\s*$/);
      if (match && match[2]) labels[match[1]] = match[2];
    });
    comp.pinLabels = labels;
    render();
  });

  componentColor.addEventListener''',
    "component editor event handlers",
)

app = sub(
    app,
    r'''    comp\.fillColor = null;\n    comp\.textColor = null;\n    comp\.fontSize = 12;''',
    '''    comp.title = "";
    comp.value = components[comp.type] && components[comp.type].defaultValue || "";
    comp.pinLabels = {};
    comp.fillColor = null;
    comp.textColor = null;
    comp.fontSize = 12;''',
    "reset component metadata",
)

Path("app.js").write_text(app)

html = Path("index.html").read_text()
html = sub(
    html,
    r'''      <section id="componentTools" hidden>\n        <h2>Component</h2>\n        <div class="tool-row">''',
    '''      <section id="componentTools" hidden>
        <h2>Component</h2>
        <label>Display name
          <input id="componentTitle" type="text" maxlength="120" placeholder="Use library name">
        </label>
        <label>Value / note
          <input id="componentValue" type="text" maxlength="160" placeholder="220Ω, LED #1, etc.">
        </label>
        <label>Pin label overrides
          <textarea id="componentPinLabels" rows="5" spellcheck="false" placeholder="p1 = GPIO1&#10;p2 = GPIO2&#10;p14 = 3V3"></textarea>
        </label>
        <p class="hint">Optional. One pin per line as <code>pin-id = label</code>. This changes only this placed component.</p>
        <div class="tool-row">''',
    "component editor markup",
)
html = sub(
    html,
    r'Click a library part to add it\. Drag to move\. Double-click a component to rename/value it\. Click pins to wire\.',
    'Click a library part to add it. Drag to move. Select a component to edit its name, value, pin labels, style, scale, or rotation. Click pins to wire.',
    "footer help",
)
Path("index.html").write_text(html)
