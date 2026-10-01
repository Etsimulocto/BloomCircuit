#!/usr/bin/env python3
"""HAPPY JARZ Controller v0.3.1 — adds ESP32 Wi-Fi scan/selection UI.

This is intentionally a thin layer over the known-good v0.3.0 controller.
The parent controller keeps ownership of serial, lights, clock, alarms, display,
diagnostics, and password redaction. This layer only adds network discovery and
SSID selection.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import happyjarz_controller as base


class HappyJarzApp(base.HappyJarzApp):
    def __init__(self):
        self.wifi_scan_rows: dict[str, str] = {}
        self.wifi_scan_state = tk.StringVar(value="Not scanned yet")
        self.wifi_scan_list = None
        super().__init__()
        self.title(f"{base.APP_NAME} v0.3.1")
        self._log("Wi-Fi scan/select layer v0.3.1 active")

    def _build_setup_tab(self, root):
        # Keep every existing setup control exactly as-is.
        super()._build_setup_tab(root)

        outer, scan = self._card(root, 10)
        outer.pack(fill="both", expand=True, pady=(8, 0))

        head = ttk.Frame(scan, style="Panel.TFrame")
        head.pack(fill="x")
        ttk.Label(head, text="VISIBLE 2.4 GHz WI-FI NETWORKS", style="Section.TLabel").pack(side="left")
        ttk.Label(head, textvariable=self.wifi_scan_state, style="PanelMuted.TLabel").pack(side="right")

        ttk.Label(
            scan,
            text="These are networks the ESP32-S3 itself can see. Select one, then enter its password above and press Send Wi-Fi.",
            style="PanelMuted.TLabel",
        ).pack(anchor="w", pady=(5, 7))

        body = ttk.Frame(scan, style="Panel.TFrame")
        body.pack(fill="both", expand=True)

        self.wifi_scan_list = tk.Listbox(
            body,
            height=7,
            bg="#080d18",
            fg="#eef3ff",
            selectbackground="#8b5cf6",
            selectforeground="#ffffff",
            relief="flat",
            bd=0,
            font=("TkFixedFont", 10),
            activestyle="none",
        )
        scroll = ttk.Scrollbar(body, orient="vertical", command=self.wifi_scan_list.yview)
        self.wifi_scan_list.configure(yscrollcommand=scroll.set)
        self.wifi_scan_list.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.wifi_scan_list.bind("<<ListboxSelect>>", self._select_scanned_network)
        self.wifi_scan_list.bind("<Double-Button-1>", self._select_scanned_network)

        row = ttk.Frame(scan, style="Panel.TFrame")
        row.pack(fill="x", pady=(8, 0))
        ttk.Button(row, text="SCAN WI-FI", style="Accent.TButton", command=self._scan_wifi).pack(side="left")
        ttk.Button(row, text="Use Selected", command=self._select_scanned_network).pack(side="left", padx=6)
        ttk.Button(row, text="Get Wi-Fi Status", command=lambda: self.link.send("GET WIFI STATUS")).pack(side="left")

    def _scan_wifi(self):
        if self.wifi_scan_list is not None:
            self.wifi_scan_list.delete(0, "end")
        self.wifi_scan_rows.clear()
        self.wifi_scan_state.set("Scanning…")
        self.link.send("SCAN WIFI")

    def _select_scanned_network(self, _event=None):
        if self.wifi_scan_list is None:
            return
        selected = self.wifi_scan_list.curselection()
        if not selected:
            return
        display = self.wifi_scan_list.get(selected[0])
        ssid = self.wifi_scan_rows.get(display)
        if ssid is not None:
            self.wifi_ssid.set(ssid)
            self.wifi_scan_state.set(f"Selected: {ssid}")

    def _handle_line(self, line: str):
        if line.startswith("HJ|WIFI_SCAN|BEGIN"):
            if self.wifi_scan_list is not None:
                self.wifi_scan_list.delete(0, "end")
            self.wifi_scan_rows.clear()
            self.wifi_scan_state.set("Scanning…")
            self._log(f"RX  {line}")
            return

        if line.startswith("HJ|WIFI_SCAN|NET|"):
            fields = self._parse_fields(line)
            ssid = fields.get("ssid", "")
            if not ssid:
                return
            rssi = fields.get("rssi", "?")
            channel = fields.get("channel", "?")
            security = fields.get("security", fields.get("enc", "?"))
            display = f"{ssid:<32.32}  {rssi:>4} dBm   CH {channel:>2}   {security}"
            # Duplicate mesh APs can share one SSID; keep the strongest line.
            previous = next((row for row, name in self.wifi_scan_rows.items() if name == ssid), None)
            if previous and self.wifi_scan_list is not None:
                try:
                    old_index = list(self.wifi_scan_list.get(0, "end")).index(previous)
                    self.wifi_scan_list.delete(old_index)
                    self.wifi_scan_rows.pop(previous, None)
                except (ValueError, tk.TclError):
                    pass
            self.wifi_scan_rows[display] = ssid
            if self.wifi_scan_list is not None:
                self.wifi_scan_list.insert("end", display)
            return

        if line.startswith("HJ|WIFI_SCAN|END|"):
            fields = self._parse_fields(line)
            count = fields.get("count", str(len(self.wifi_scan_rows)))
            self.wifi_scan_state.set(f"{count} visible network(s)")
            self._log(f"RX  {line}")
            return

        super()._handle_line(line)


if __name__ == "__main__":
    HappyJarzApp().mainloop()
