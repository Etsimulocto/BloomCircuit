#!/usr/bin/env python3
"""HAPPY JARZ Controller v0.3.2 — editable business/custom marquee sayings."""

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
        super().__init__()
        self.title("HAPPY JARZ Controller v0.3.2")
        self._log("Custom business marquee editor v0.3.2 active")

    def _build_display_tab(self, root):
        super()._build_display_tab(root)

        if self.custom_saying_source is None:
            self.custom_saying_source = tk.StringVar(master=self, value="BUILTIN")
        if self.custom_saying_state is None:
            self.custom_saying_state = tk.StringVar(master=self, value="8 custom slots stored in jar")

        outer, panel = self._card(root, 10)
        outer.pack(fill="both", expand=True, pady=(8, 0))

        head = ttk.Frame(panel, style="Panel.TFrame")
        head.pack(fill="x")
        ttk.Label(head, text="CUSTOM MARQUEE SAYINGS", style="Section.TLabel").pack(side="left")
        ttk.Label(head, textvariable=self.custom_saying_state, style="PanelMuted.TLabel").pack(side="right")

        ttk.Label(
            panel,
            text="For banks, clinics, shops, offices, events, gifts, etc. Enter up to 8 messages, one per line. Each message is saved inside the jar and survives unplugging.",
            style="PanelMuted.TLabel",
        ).pack(anchor="w", pady=(5, 7))

        body = ttk.Frame(panel, style="Panel.TFrame")
        body.pack(fill="both", expand=True)
        self.custom_saying_text = tk.Text(
            body,
            height=8,
            wrap="none",
            bg="#080d18",
            fg="#eef3ff",
            insertbackground="#ffffff",
            selectbackground="#3b4d70",
            relief="flat",
            bd=0,
            padx=8,
            pady=6,
            font=("TkFixedFont", 10),
        )
        scroll = ttk.Scrollbar(body, orient="vertical", command=self.custom_saying_text.yview)
        self.custom_saying_text.configure(yscrollcommand=scroll.set)
        self.custom_saying_text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        controls = ttk.Frame(panel, style="Panel.TFrame")
        controls.pack(fill="x", pady=(8, 0))
        ttk.Label(controls, text="Screensaver sayings:", style="PanelMuted.TLabel").pack(side="left")
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

        # Clear first so deleted/shortened lists do not leave stale slots behind.
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


if __name__ == "__main__":
    HappyJarzApp().mainloop()
