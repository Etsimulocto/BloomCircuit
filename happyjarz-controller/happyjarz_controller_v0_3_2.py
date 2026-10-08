#!/usr/bin/env python3
"""HAPPY JARZ Controller v0.3.2 — current OLED/saver controls + editable marquee sayings."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import happyjarz_controller_v0_3_1 as previous


class HappyJarzApp(previous.HappyJarzApp):
    def __init__(self):
        self.custom_saying_source = None
        self.custom_saying_text = None
        self.custom_saying_state = None
        self._custom_saying_rx: dict[int, str] = {}
        self.saver_state = None
        super().__init__()
        self.title("HAPPY JARZ Controller v0.3.2")
        self._log("Current OLED screensaver controls + custom marquee editor active")

    def _build_display_tab(self, root):
        if self.custom_saying_source is None:
            self.custom_saying_source = tk.StringVar(master=self, value="BUILTIN")
        if self.custom_saying_state is None:
            self.custom_saying_state = tk.StringVar(master=self, value="8 custom slots stored in jar")
        if self.saver_state is None:
            self.saver_state = tk.StringVar(master=self, value="Idle • auto-start after 10 seconds")

        outer, display = self._card(root, 10)
        outer.pack(fill="x", pady=(0, 8))

        head = ttk.Frame(display, style="Panel.TFrame")
        head.pack(fill="x")
        ttk.Label(head, text="OLED + PROCEDURAL SCREENSAVERS", style="Section.TLabel").pack(side="left")
        ttk.Label(head, textvariable=self.saver_state, style="PanelMuted.TLabel").pack(side="right")

        preview = ttk.Frame(display, style="Panel.TFrame")
        preview.pack(fill="x", pady=(8, 8))

        screen_box = tk.Frame(preview, bg="#05080d", bd=1, relief="sunken")
        screen_box.pack(side="left")

        saver_oled_label = tk.Label(
            screen_box,
            image=self.oled_scaled_image,
            bg="#000000",
            bd=0,
            padx=0,
            pady=0,
        )
        saver_oled_label.pack(padx=6, pady=6)
        self.oled_mirror_labels.append(saver_oled_label)

        preview_info = ttk.Frame(preview, style="Panel.TFrame")
        preview_info.pack(side="left", fill="both", expand=True, padx=(12, 0))
        ttk.Label(
            preview_info,
            text="LIVE DEVICE OLED",
            style="Section.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            preview_info,
            textvariable=self.oled_mirror_status,
            style="Value.TLabel",
        ).pack(anchor="w", pady=(4, 4))
        ttk.Label(
            preview_info,
            text="Actual 128x64 framebuffer from the Jar. Saver buttons below update this view and the physical OLED together.",
            style="PanelMuted.TLabel",
            wraplength=520,
        ).pack(anchor="w")

        info = ttk.Frame(display, style="Panel.TFrame")
        info.pack(fill="x", pady=(8, 7))
        ttk.Label(info, text="Idle delay", style="PanelMuted.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(info, text="10 seconds", style="Value.TLabel").grid(row=0, column=1, sticky="w", padx=(10, 24))
        ttk.Label(info, text="Modes", style="PanelMuted.TLabel").grid(row=0, column=2, sticky="w")
        ttk.Label(info, text="SAYINGS • SPIRAL • TRIPPY • PARTICLES • BLOOM • BREATHE • GLITTER", style="Value.TLabel").grid(row=0, column=3, sticky="w", padx=(10, 0))

        ttk.Label(
            display,
            text="On the jar: LEFT / RIGHT = change saver • B = exit • ART: UP/DOWN = speed, A = NEW UNIVERSE from live board entropy",
            style="PanelMuted.TLabel",
        ).pack(anchor="w", pady=(1, 7))

        row = ttk.Frame(display, style="Panel.TFrame")
        row.pack(fill="x")
        ttk.Button(row, text="SAYINGS", command=lambda: self.link.send("SET SAVER MODE SAYINGS")).pack(side="left")
        ttk.Button(row, text="SPIRAL", command=lambda: self.link.send("SET SAVER MODE SPIRAL")).pack(side="left", padx=5)
        ttk.Button(row, text="TRIPPY", command=lambda: self.link.send("SET SAVER MODE TRIPPY")).pack(side="left")
        ttk.Button(row, text="PARTICLES", command=lambda: self.link.send("SET SAVER MODE PARTICLES")).pack(side="left", padx=5)
        ttk.Button(row, text="BLOOM", command=lambda: self.link.send("SET SAVER MODE BLOOM")).pack(side="left")
        ttk.Button(row, text="BREATHE", command=lambda: self.link.send("SET SAVER MODE BREATHE")).pack(side="left", padx=5)
        ttk.Button(row, text="GLITTER", command=lambda: self.link.send("SET SAVER MODE GLITTER")).pack(side="left")
        ttk.Button(row, text="NEW UNIVERSE (A)", style="Accent.TButton", command=lambda: self.link.send("SAVER RESEED")).pack(side="left", padx=(8, 5))
        ttk.Button(row, text="SPEED −", command=lambda: self.link.send("SAVER SPEED DOWN")).pack(side="left")
        ttk.Button(row, text="SPEED +", command=lambda: self.link.send("SAVER SPEED UP")).pack(side="left", padx=5)
        ttk.Button(row, text="EXIT (B)", command=lambda: self.link.send("SAVER EXIT")).pack(side="left")
        ttk.Button(row, text="Refresh", command=lambda: self.link.send("GET SAVER STATUS")).pack(side="right")

        ttk.Label(
            display,
            text="PARTICLES: tiny gravity universe • BLOOM: opening/closing lotus • BREATHE: slow geometric fade illusion • GLITTER: falling mixed-shape sparkle field.",
            style="PanelMuted.TLabel",
        ).pack(anchor="w", pady=(7, 0))

        outer, mapping = self._card(root, 9)
        outer.pack(fill="x", pady=(0, 8))
        ttk.Label(mapping, text="CONTROL MAP", style="Section.TLabel").pack(anchor="w")
        ttk.Label(
            mapping,
            text="HOME: A/B colors • UP/DOWN patterns • RIGHT menu     |     SAVER: LEFT/RIGHT mode • B exit • ART: UP/DOWN speed • A reseed",
            style="PanelMuted.TLabel",
        ).pack(anchor="w", pady=(5, 7))
        row = ttk.Frame(mapping, style="Panel.TFrame")
        row.pack(fill="x")
        for label, command in (
            ("JAR MODE", "SET INPUT MODE JAR"),
            ("MENU MODE", "SET INPUT MODE MENU"),
            ("GAME MODE", "SET INPUT MODE GAME"),
            ("TEST INPUT", "TEST INPUT"),
            ("GET INPUT", "GET INPUT"),
        ):
            ttk.Button(row, text=label, command=lambda c=command: self.link.send(c)).pack(side="left", padx=(0, 6))

        outer, panel = self._card(root, 9)
        outer.pack(fill="both", expand=True)

        head = ttk.Frame(panel, style="Panel.TFrame")
        head.pack(fill="x")
        ttk.Label(head, text="CUSTOM MARQUEE SAYINGS", style="Section.TLabel").pack(side="left")
        ttk.Label(head, textvariable=self.custom_saying_state, style="PanelMuted.TLabel").pack(side="right")

        ttk.Label(
            panel,
            text="For banks, clinics, shops, offices, events, gifts, etc. Up to 8 messages; each is saved inside the jar and survives unplugging.",
            style="PanelMuted.TLabel",
        ).pack(anchor="w", pady=(5, 6))

        body = ttk.Frame(panel, style="Panel.TFrame")
        body.pack(fill="both", expand=True)
        self.custom_saying_text = tk.Text(
            body,
            height=6,
            wrap="none",
            bg="#080d18",
            fg="#eef3ff",
            insertbackground="#ffffff",
            selectbackground="#3b4d70",
            relief="flat",
            bd=0,
            padx=8,
            pady=5,
            font=("TkFixedFont", 10),
        )
        scroll = ttk.Scrollbar(body, orient="vertical", command=self.custom_saying_text.yview)
        self.custom_saying_text.configure(yscrollcommand=scroll.set)
        self.custom_saying_text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        controls = ttk.Frame(panel, style="Panel.TFrame")
        controls.pack(fill="x", pady=(7, 0))
        ttk.Label(controls, text="SAYINGS source:", style="PanelMuted.TLabel").pack(side="left")
        source = ttk.Combobox(
            controls,
            state="readonly",
            width=10,
            textvariable=self.custom_saying_source,
            values=("BUILTIN", "CUSTOM", "MIXED"),
        )
        source.pack(side="left", padx=(6, 10))
        ttk.Button(controls, text="LOAD FROM JAR", command=self._load_custom_sayings).pack(side="left")
        ttk.Button(controls, text="SEND + SAVE", style="Accent.TButton", command=self._send_custom_sayings).pack(side="left", padx=6)
        ttk.Button(controls, text="CLEAR CUSTOM", style="Danger.TButton", command=self._clear_custom_sayings).pack(side="left")

    def _load_custom_sayings(self):
        self._custom_saying_rx.clear()
        if self.custom_saying_state is not None:
            self.custom_saying_state.set("Loading from jar…")
        self.link.send("GET CUSTOM SAYINGS")

    def _send_custom_sayings(self):
        if self.custom_saying_text is None:
            return
        raw_lines = self.custom_saying_text.get("1.0", "end-1c").splitlines()
        lines = []
        for raw in raw_lines:
            text = raw.strip().replace("|", "/")
            if text:
                lines.append(text[:96])
            if len(lines) >= 8:
                break

        self.link.send("CLEAR CUSTOM SAYINGS")
        for slot, text in enumerate(lines, start=1):
            self.link.send(f"SET CUSTOM SAYING {slot} {text}")

        source = (self.custom_saying_source.get() if self.custom_saying_source is not None else "BUILTIN").strip().upper()
        if source not in ("BUILTIN", "CUSTOM", "MIXED"):
            source = "BUILTIN"
        self.link.send(f"SET SAYING SOURCE {source}")
        if self.custom_saying_state is not None:
            self.custom_saying_state.set(f"Saved {len(lines)} custom message(s) • {source}")

    def _clear_custom_sayings(self):
        self.link.send("CLEAR CUSTOM SAYINGS")
        if self.custom_saying_text is not None:
            self.custom_saying_text.delete("1.0", "end")
        if self.custom_saying_source is not None:
            self.custom_saying_source.set("BUILTIN")
        self.link.send("SET SAYING SOURCE BUILTIN")
        if self.custom_saying_state is not None:
            self.custom_saying_state.set("Custom sayings cleared")

    def _handle_line(self, line: str):
        if line.startswith("HJ|SAVER|"):
            fields = self._parse_fields(line)
            active = fields.get("active", "0") in ("1", "true", "TRUE")
            mode = fields.get("mode", "SAYINGS")
            state = "ACTIVE" if active else "idle"
            if mode == "SPIRAL":
                detail = f"speed {fields.get('spiral_speed', '1')}/8"
            elif mode == "TRIPPY":
                detail = f"speed {fields.get('trippy_speed', '1')}/8"
            elif mode == "PARTICLES":
                detail = (
                    f"speed {fields.get('particle_speed', '1')}/8 • "
                    f"{fields.get('particles', '?')} particles • "
                    f"{fields.get('attractors', '?')} wells • "
                    f"links {fields.get('links', '?')} • wrap {fields.get('wrap', '?')} • repel {fields.get('repel', '?')}"
                )
            elif mode in ("BLOOM", "BREATHE", "GLITTER"):
                detail = f"speed {fields.get('visual_speed', '1')}/8"
            else:
                detail = "marquee"
            if self.saver_state is not None:
                self.saver_state.set(f"{mode} • {state} • {detail}")
            self._log(f"RX  {line}")
            return

        if line.startswith("HJ|CUSTOM_SAYINGS|BEGIN|"):
            fields = self._parse_fields(line)
            self._custom_saying_rx.clear()
            source = fields.get("source", "BUILTIN")
            if self.custom_saying_source is not None:
                self.custom_saying_source.set(source)
            if self.custom_saying_state is not None:
                self.custom_saying_state.set("Receiving…")
            self._log(f"RX  {line}")
            return

        if line.startswith("HJ|CUSTOM_SAYING|"):
            fields = self._parse_fields(line)
            try:
                slot = int(fields.get("slot", "0"))
            except ValueError:
                slot = 0
            if 1 <= slot <= 8:
                self._custom_saying_rx[slot] = fields.get("text", "")
            return

        if line.startswith("HJ|CUSTOM_SAYINGS|END|"):
            fields = self._parse_fields(line)
            source = fields.get("source", "BUILTIN")
            if self.custom_saying_source is not None:
                self.custom_saying_source.set(source)
            if self.custom_saying_text is not None:
                self.custom_saying_text.delete("1.0", "end")
                values = [self._custom_saying_rx.get(i, "") for i in range(1, 9)]
                while values and not values[-1]:
                    values.pop()
                self.custom_saying_text.insert("1.0", "\n".join(values))
            count = sum(1 for value in self._custom_saying_rx.values() if value)
            if self.custom_saying_state is not None:
                self.custom_saying_state.set(f"Loaded {count} custom message(s) • {source}")
            self._log(f"RX  {line}")
            return

        super()._handle_line(line)
        if line.startswith("HJ|IDENTITY|"):
            self.after(150, lambda: self.link.send("GET SAVER STATUS"))


if __name__ == "__main__":
    HappyJarzApp().mainloop()
