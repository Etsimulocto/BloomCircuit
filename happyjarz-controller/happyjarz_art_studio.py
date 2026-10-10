#!/usr/bin/env python3
"""A small native 128x64 monochrome editor for the HAPPY JARZ controller."""

from __future__ import annotations

import json
import math
import os
import re
import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

WIDTH = 128
HEIGHT = 64
SCALE = 6
PIXELS = WIDTH * HEIGHT
STAMP_NAMES = ("Star", "Heart", "Diamond", "Spark", "Smiley", "Flower")
CATEGORIES = ("Faces", "Emojis", "Art", "Game")


def pack_xbm(pixels: list[int] | tuple[int, ...]) -> bytes:
    """Pack row-major monochrome pixels in XBM/U8g2 LSB-first byte order."""
    if len(pixels) != PIXELS:
        raise ValueError(f"expected {PIXELS} pixels, got {len(pixels)}")
    output = bytearray(WIDTH // 8 * HEIGHT)
    for y in range(HEIGHT):
        for x in range(WIDTH):
            if pixels[y * WIDTH + x]:
                output[y * (WIDTH // 8) + (x >> 3)] |= 1 << (x & 7)
    return bytes(output)


def circle_points(center_x: int, center_y: int, radius: int) -> set[tuple[int, int]]:
    """Return a clipped, one-pixel outline circle."""
    if radius < 1:
        return {(center_x, center_y)}
    points: set[tuple[int, int]] = set()
    outer = radius * radius
    inner = max(0, radius - 1) ** 2
    for y in range(center_y - radius, center_y + radius + 1):
        for x in range(center_x - radius, center_x + radius + 1):
            distance = (x - center_x) ** 2 + (y - center_y) ** 2
            if inner <= distance <= outer and 0 <= x < WIDTH and 0 <= y < HEIGHT:
                points.add((x, y))
    return points


def _inside_polygon(x: float, y: float, vertices: list[tuple[float, float]]) -> bool:
    inside = False
    j = len(vertices) - 1
    for i, (xi, yi) in enumerate(vertices):
        xj, yj = vertices[j]
        if ((yi > y) != (yj > y)) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi:
            inside = not inside
        j = i
    return inside


def stamp_points(name: str, center_x: int, center_y: int, scale: int = 1) -> set[tuple[int, int]]:
    """Create a filled, clipped monochrome stamp mask."""
    scale = max(1, min(3, int(scale)))
    radius = 7 * scale
    vertices: list[tuple[float, float]] = []
    if name == "Star":
        for i in range(10):
            angle = -math.pi / 2 + i * math.pi / 5
            r = radius if i % 2 == 0 else radius * 0.44
            vertices.append((center_x + math.cos(angle) * r, center_y + math.sin(angle) * r))
    points: set[tuple[int, int]] = set()
    for y in range(center_y - radius - 1, center_y + radius + 2):
        for x in range(center_x - radius - 1, center_x + radius + 2):
            dx = (x - center_x) / scale
            dy = (y - center_y) / scale
            keep = False
            if name == "Star":
                keep = _inside_polygon(x, y, vertices)
            elif name == "Diamond":
                keep = abs(dx) + abs(dy) <= 7
            elif name == "Heart":
                px = dx / 6.2
                py = -(dy - 1.3) / 5.8
                q = px * px + py * py - 1
                keep = q * q * q - px * px * py * py * py <= 0
            elif name == "Spark":
                keep = (abs(dx) <= 0.85 and abs(dy) <= 7) or (abs(dy) <= 0.85 and abs(dx) <= 7)
                keep = keep or (abs(dx - dy) <= 0.7 and abs(dx) <= 4)
                keep = keep or (abs(dx + dy) <= 0.7 and abs(dx) <= 4)
            elif name == "Smiley":
                d = dx * dx + dy * dy
                keep = 35 <= d <= 49
                keep = keep or (abs(dx + 3) <= 0.8 and abs(dy + 2) <= 1)
                keep = keep or (abs(dx - 3) <= 0.8 and abs(dy + 2) <= 1)
                if -3 <= dx <= 3 and 0 <= dy <= 4:
                    keep = keep or abs(dy - (2 + (dx * dx) / 4)) <= 0.8
            elif name == "Flower":
                keep = (dx * dx + (dy - 5) ** 2 <= 12 or
                        dx * dx + (dy + 5) ** 2 <= 12 or
                        (dx - 5) ** 2 + dy * dy <= 12 or
                        (dx + 5) ** 2 + dy * dy <= 12 or
                        (dx * dx + dy * dy <= 8))
            if keep and 0 <= x < WIDTH and 0 <= y < HEIGHT:
                points.add((x, y))
    return points


def _line_points(a: tuple[int, int], b: tuple[int, int]) -> set[tuple[int, int]]:
    x0, y0 = a
    x1, y1 = b
    points: set[tuple[int, int]] = set()
    dx, sx = abs(x1 - x0), 1 if x0 < x1 else -1
    dy, sy = -abs(y1 - y0), 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        if 0 <= x0 < WIDTH and 0 <= y0 < HEIGHT:
            points.add((x0, y0))
        if x0 == x1 and y0 == y1:
            return points
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


class HappyJarzArtStudio(ttk.Frame):
    """A Tkinter pixel editor embedded in the controller's OLED ART tab."""

    def __init__(self, parent: tk.Misc):
        super().__init__(parent)
        self.pixels = [0] * PIXELS
        self.tool = "Pencil"
        self.draw_color = 1
        self.mirror = tk.BooleanVar(value=False)
        self.stamp_name = tk.StringVar(value=STAMP_NAMES[0])
        self.stamp_size = tk.IntVar(value=1)
        self.name_var = tk.StringVar(value="Happy Face")
        self.category_var = tk.StringVar(value="Faces")
        self.status_var = tk.StringVar(value="128 × 64 • 1,024 bytes per image")
        self.history: list[list[int]] = []
        self.redo_history: list[list[int]] = []
        self.start_point: tuple[int, int] | None = None
        self.before_shape: list[int] | None = None
        self.assets: list[dict] = []
        self.asset_path = Path.home() / ".happyjarz" / "art_library.json"
        self._build_ui()
        self._load_library()
        self._render_all()

    def _build_ui(self) -> None:
        head = ttk.Frame(self)
        head.pack(fill="x", pady=(0, 7))
        ttk.Label(head, text="128 × 64 OLED pixel art", style="Section.TLabel").pack(side="left")
        ttk.Label(head, textvariable=self.status_var, style="PanelMuted.TLabel").pack(side="right")

        meta = ttk.Frame(self)
        meta.pack(fill="x", pady=(0, 7))
        ttk.Label(meta, text="Name").pack(side="left")
        ttk.Entry(meta, textvariable=self.name_var, width=20).pack(side="left", padx=(5, 10))
        ttk.Label(meta, text="Group").pack(side="left")
        ttk.Combobox(meta, textvariable=self.category_var, values=CATEGORIES,
                     state="readonly", width=9).pack(side="left", padx=5)
        ttk.Button(meta, text="New", command=self.new_art).pack(side="left", padx=(6, 3))
        ttk.Button(meta, text="Save", style="Accent.TButton", command=self.save_art).pack(side="left", padx=3)
        ttk.Button(meta, text="Export U8g2 .h", command=self.export_header).pack(side="left", padx=3)
        ttk.Button(meta, text="Undo", command=self.undo).pack(side="right", padx=(3, 0))
        ttk.Button(meta, text="Redo", command=self.redo).pack(side="right", padx=3)

        tools = ttk.Frame(self)
        tools.pack(fill="x", pady=(0, 8))
        self.tool_buttons: dict[str, tk.Button] = {}
        for name in ("Pencil", "Eraser", "Fill", "Line", "Rectangle", "Circle", "Stamp"):
            b = tk.Button(tools, text=name, padx=8, pady=4, relief="raised",
                          command=lambda value=name: self.set_tool(value))
            b.pack(side="left", padx=(0, 4))
            self.tool_buttons[name] = b
        self.set_tool("Pencil")
        ttk.Label(tools, text="Stamp").pack(side="left", padx=(8, 3))
        ttk.Combobox(tools, textvariable=self.stamp_name, values=STAMP_NAMES,
                     state="readonly", width=9).pack(side="left")
        ttk.Label(tools, text="Size").pack(side="left", padx=(8, 3))
        ttk.Combobox(tools, textvariable=self.stamp_size, values=(1, 2, 3),
                     state="readonly", width=3).pack(side="left")
        ttk.Checkbutton(tools, text="Mirror", variable=self.mirror).pack(side="left", padx=8)
        ttk.Button(tools, text="Black", command=lambda: self.set_color(1)).pack(side="left", padx=(3, 2))
        ttk.Button(tools, text="White", command=lambda: self.set_color(0)).pack(side="left", padx=2)
        ttk.Button(tools, text="Clear", command=self.clear).pack(side="right")

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        left = ttk.Frame(body)
        left.pack(side="left", fill="both", expand=True)
        self.canvas = tk.Canvas(left, width=WIDTH * SCALE, height=HEIGHT * SCALE,
                                bg="#ffffff", highlightthickness=1, highlightbackground="#8d9289",
                                cursor="crosshair", takefocus=True)
        self.canvas.pack(anchor="nw", expand=True)
        self.canvas.bind("<Button-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.canvas.bind("<KeyPress-z>", lambda _e: self.undo())
        self.canvas.bind("<KeyPress-y>", lambda _e: self.redo())

        side = ttk.Frame(body, padding=(12, 0, 0, 0))
        side.pack(side="right", fill="y")
        ttk.Label(side, text="SCREEN PREVIEW", style="Section.TLabel").pack(anchor="w")
        self.preview = tk.Canvas(side, width=256, height=128, bg="#ffffff",
                                 highlightthickness=4, highlightbackground="#39483d")
        self.preview.pack(pady=(6, 11))
        ttk.Label(side, text="MY PICTURES", style="Section.TLabel").pack(anchor="w")
        list_frame = ttk.Frame(side)
        list_frame.pack(fill="both", expand=True, pady=(5, 6))
        self.asset_list = tk.Listbox(list_frame, width=24, height=10, exportselection=False)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.asset_list.yview)
        self.asset_list.configure(yscrollcommand=scrollbar.set)
        self.asset_list.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.asset_list.bind("<<ListboxSelect>>", self._select_asset)
        row = ttk.Frame(side)
        row.pack(fill="x")
        ttk.Button(row, text="Load", command=self.load_selected).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Delete", command=self.delete_selected).pack(side="left", fill="x", expand=True, padx=(5, 0))

        ttk.Label(self, text="Circle: drag from center to radius • Stamps place a filled little shape • Save keeps art on this Pi",
                  style="PanelMuted.TLabel").pack(anchor="w", pady=(6, 0))

    def set_tool(self, value: str) -> None:
        self.tool = value
        for name, button in self.tool_buttons.items():
            button.configure(relief="sunken" if name == value else "raised",
                             bg="#dce9d8" if name == value else "#efeee8")

    def set_color(self, value: int) -> None:
        self.draw_color = 1 if value else 0
        self.status_var.set("Drawing black pixels" if self.draw_color else "Erasing to white")

    def _push_undo(self) -> None:
        self.history.append(self.pixels.copy())
        if len(self.history) > 50:
            self.history.pop(0)
        self.redo_history.clear()

    def undo(self) -> None:
        if not self.history:
            return
        self.redo_history.append(self.pixels.copy())
        self.pixels = self.history.pop()
        self._render_all()

    def redo(self) -> None:
        if not self.redo_history:
            return
        self.history.append(self.pixels.copy())
        self.pixels = self.redo_history.pop()
        self._render_all()

    def clear(self) -> None:
        self._push_undo()
        self.pixels = [0] * PIXELS
        self._render_all()
        self.status_var.set("Canvas cleared • Save to keep it")

    def new_art(self) -> None:
        self._push_undo()
        self.pixels = [0] * PIXELS
        self.name_var.set("Untitled")
        self.category_var.set("Art")
        self.asset_list.selection_clear(0, "end")
        self._render_all()
        self.status_var.set("New blank canvas • Save to add it to your pictures")

    def _point(self, event: tk.Event) -> tuple[int, int]:
        x = max(0, min(WIDTH - 1, event.x // SCALE))
        y = max(0, min(HEIGHT - 1, event.y // SCALE))
        return x, y

    def _set_pixel(self, x: int, y: int, value: int) -> None:
        if not (0 <= x < WIDTH and 0 <= y < HEIGHT):
            return
        self.pixels[y * WIDTH + x] = value
        if self.mirror.get():
            self.pixels[y * WIDTH + WIDTH - 1 - x] = value
        self._draw_cell(x, y)
        if self.mirror.get():
            self._draw_cell(WIDTH - 1 - x, y)

    def _apply_points(self, points: set[tuple[int, int]], value: int | None = None) -> None:
        value = self.draw_color if value is None else value
        for x, y in points:
            self._set_pixel(x, y, value)

    def _press(self, event: tk.Event) -> None:
        self.canvas.focus_set()
        point = self._point(event)
        self._push_undo()
        if self.tool == "Fill":
            self._flood_fill(*point, self.draw_color)
            self._render_all()
            return
        if self.tool == "Stamp":
            self._apply_points(stamp_points(self.stamp_name.get(), *point, self.stamp_size.get()))
            self._render_all()
            return
        self.start_point = point
        self.before_shape = self.pixels.copy()
        if self.tool in ("Pencil", "Eraser"):
            self._paint_brush(*point)

    def _drag(self, event: tk.Event) -> None:
        if self.start_point is None:
            return
        point = self._point(event)
        if self.tool in ("Pencil", "Eraser"):
            self._apply_points(_line_points(self._last_point, point), 0 if self.tool == "Eraser" else self.draw_color)
            self._last_point = point
        else:
            previous_pixels = self.pixels
            self.pixels = self.before_shape.copy() if self.before_shape is not None else self.pixels
            if self.tool == "Line":
                self._apply_points(_line_points(self.start_point, point))
            elif self.tool == "Rectangle":
                self._apply_points(self._rectangle_points(self.start_point, point))
            elif self.tool == "Circle":
                dx, dy = point[0] - self.start_point[0], point[1] - self.start_point[1]
                self._apply_points(circle_points(self.start_point[0], self.start_point[1], int(math.hypot(dx, dy))))
            self._render_changed(previous_pixels)

    def _release(self, _event: tk.Event) -> None:
        if self.start_point is not None:
            self.start_point = None
            self.before_shape = None
            self.status_var.set("128 × 64 • 1,024 bytes per image • Save to keep it")

    def _paint_brush(self, x: int, y: int) -> None:
        value = 0 if self.tool == "Eraser" else self.draw_color
        self._set_pixel(x, y, value)
        self._last_point = (x, y)

    @staticmethod
    def _rectangle_points(a: tuple[int, int], b: tuple[int, int]) -> set[tuple[int, int]]:
        x0, x1 = sorted((a[0], b[0]))
        y0, y1 = sorted((a[1], b[1]))
        points = set()
        for x in range(x0, x1 + 1):
            points.add((x, y0))
            points.add((x, y1))
        for y in range(y0, y1 + 1):
            points.add((x0, y))
            points.add((x1, y))
        return points

    def _flood_fill(self, x: int, y: int, value: int) -> None:
        index = y * WIDTH + x
        old = self.pixels[index]
        if old == value:
            return
        stack = [(x, y)]
        while stack:
            px, py = stack.pop()
            if not (0 <= px < WIDTH and 0 <= py < HEIGHT):
                continue
            i = py * WIDTH + px
            if self.pixels[i] != old:
                continue
            self.pixels[i] = value
            if self.mirror.get():
                self.pixels[py * WIDTH + WIDTH - 1 - px] = value
            stack.extend(((px + 1, py), (px - 1, py), (px, py + 1), (px, py - 1)))

    def _draw_cell(self, x: int, y: int) -> None:
        value = self.pixels[y * WIDTH + x]
        color = "#151812" if value else "#ffffff"
        x0, y0 = x * SCALE, y * SCALE
        self.canvas.delete(f"pixel-{x}-{y}")
        if value:
            self.canvas.create_rectangle(x0, y0, x0 + SCALE, y0 + SCALE, fill=color, outline="",
                                         tags=(f"pixel-{x}-{y}",))
        px0, py0 = x * 2, y * 2
        self.preview.delete(f"preview-{x}-{y}")
        if value:
            self.preview.create_rectangle(px0, py0, px0 + 2, py0 + 2, fill=color, outline="",
                                          tags=(f"preview-{x}-{y}",))

    def _render_all(self) -> None:
        self.canvas.delete("all")
        self.preview.delete("all")
        self.canvas.configure(bg="#ffffff")
        for y in range(HEIGHT):
            for x in range(WIDTH):
                if self.pixels[y * WIDTH + x]:
                    self._draw_cell(x, y)
        for x in range(0, WIDTH + 1, 8):
            self.canvas.create_line(x * SCALE, 0, x * SCALE, HEIGHT * SCALE, fill="#e7e9e4", width=1, tags=("grid",))
        for y in range(0, HEIGHT + 1, 8):
            self.canvas.create_line(0, y * SCALE, WIDTH * SCALE, y * SCALE, fill="#e7e9e4", width=1, tags=("grid",))

    def _render_changed(self, previous: list[int]) -> None:
        for i, (old, new) in enumerate(zip(previous, self.pixels)):
            if old != new:
                self._draw_cell(i % WIDTH, i // WIDTH)

    def _load_library(self) -> None:
        try:
            data = json.loads(self.asset_path.read_text(encoding="utf-8"))
            entries = data.get("assets", [])
            self.assets = [self._clean_asset(item) for item in entries if isinstance(item, dict)]
        except (OSError, ValueError, TypeError):
            self.assets = []
        if not self.assets:
            self.assets = [self._starter_face()]
        self._refresh_list()
        self.asset_list.selection_set(0)
        self.load_selected()

    @staticmethod
    def _clean_asset(item: dict) -> dict:
        source = item.get("pixels", [])
        values = [1 if bool(v) else 0 for v in source[:PIXELS]]
        values.extend([0] * (PIXELS - len(values)))
        category = item.get("category", "Art")
        if category not in CATEGORIES:
            category = "Art"
        return {"name": str(item.get("name", "Untitled"))[:48], "category": category, "pixels": values}

    @staticmethod
    def _starter_face() -> dict:
        pixels = [0] * PIXELS
        for y in range(8, 57):
            for x in range(40, 89):
                d = (x - 64) ** 2 + (y - 32) ** 2
                if 22 ** 2 <= d <= 24 ** 2:
                    pixels[y * WIDTH + x] = 1
        for y in range(24, 29):
            for x in (*range(51, 55), *range(74, 78)):
                pixels[y * WIDTH + x] = 1
        for x in range(50, 79):
            y = round(41 + 7 * math.sin((x - 50) / 28 * math.pi))
            pixels[y * WIDTH + x] = 1
        return {"name": "Happy Face", "category": "Faces", "pixels": pixels}

    def _refresh_list(self) -> None:
        self.asset_list.delete(0, "end")
        for item in self.assets:
            self.asset_list.insert("end", f"{item['name']}  ·  {item['category']}")

    def _select_asset(self, _event: tk.Event | None = None) -> None:
        self.load_selected()

    def load_selected(self) -> None:
        selection = self.asset_list.curselection()
        if not selection or selection[0] >= len(self.assets):
            return
        item = self.assets[selection[0]]
        self.name_var.set(item["name"])
        self.category_var.set(item["category"])
        self.pixels = item["pixels"].copy()
        self.history.clear()
        self.redo_history.clear()
        self._render_all()
        self.status_var.set(f"Loaded {item['name']} • 1,024 bytes when exported")

    def save_art(self) -> None:
        name = self.name_var.get().strip()[:48] or "Untitled"
        category = self.category_var.get() if self.category_var.get() in CATEGORIES else "Art"
        target = next((item for item in self.assets if item["name"].casefold() == name.casefold()), None)
        if target is None:
            target = {"name": name, "category": category, "pixels": self.pixels.copy()}
            self.assets.append(target)
        else:
            target.update(name=name, category=category, pixels=self.pixels.copy())
        try:
            self.asset_path.parent.mkdir(parents=True, exist_ok=True)
            fd, temp_name = tempfile.mkstemp(prefix="happyjarz-art-", suffix=".json", dir=self.asset_path.parent)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump({"version": 1, "assets": self.assets}, stream, separators=(",", ":"))
                stream.write("\n")
            os.replace(temp_name, self.asset_path)
        except OSError as exc:
            messagebox.showerror("Save art", f"Could not save the art library:\n{exc}", parent=self)
            return
        self._refresh_list()
        index = self.assets.index(target)
        self.asset_list.selection_set(index)
        self.status_var.set(f"Saved {name} to this Pi")

    def delete_selected(self) -> None:
        selection = self.asset_list.curselection()
        if not selection:
            return
        del self.assets[selection[0]]
        if not self.assets:
            self.assets = [self._starter_face()]
        self._write_library()
        self._refresh_list()
        self.asset_list.selection_set(0)
        self.load_selected()

    def _write_library(self) -> None:
        self.asset_path.parent.mkdir(parents=True, exist_ok=True)
        self.asset_path.write_text(json.dumps({"version": 1, "assets": self.assets}, separators=(",", ":")) + "\n", encoding="utf-8")

    def export_header(self) -> None:
        name = self.name_var.get().strip() or "Happy Jarz Art"
        symbol = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").lower() or "happy_jarz_art"
        if symbol[0].isdigit():
            symbol = "art_" + symbol
        path = filedialog.asksaveasfilename(parent=self, title="Export U8g2 image",
                                            initialfile=f"{symbol}.h", defaultextension=".h",
                                            filetypes=(("C header", "*.h"), ("All files", "*")))
        if not path:
            return
        data = pack_xbm(self.pixels)
        rows = []
        for start in range(0, len(data), 16):
            rows.append("  " + ", ".join(f"0x{value:02x}" for value in data[start:start + 16]))
        header = (
            f"// Happy Jarz Pixel Art • 128 x 64 • 1-bit XBM byte order\n"
            f"#pragma once\n#include <Arduino.h>\n\n"
            f"static const uint8_t {symbol}_bits[] PROGMEM = {{\n"
            + ",\n".join(rows)
            + f"\n}};\n\n// Draw with: u8g2.drawXBMP(0, 0, 128, 64, {symbol}_bits);\n"
        )
        try:
            Path(path).write_text(header, encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("Export art", f"Could not write the header:\n{exc}", parent=self)
            return
        self.status_var.set(f"Exported {Path(path).name} • 1,024 image bytes")


__all__ = ["HappyJarzArtStudio", "pack_xbm", "circle_points", "stamp_points"]
