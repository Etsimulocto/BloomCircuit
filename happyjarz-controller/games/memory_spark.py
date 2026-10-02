#!/usr/bin/env python3
"""
============================================================
BLOOMCORE MODULE
============================================================
identity:
  name: HAPPY JARZ — Memory Spark
  module: memory_spark
  version: 0.1
  format: bloomcore/v1.3

purpose:
  Standalone 128x64 landscape monochrome OLED minigame.
  Simon-style memory game using the HAPPY JARZ D-pad touch controls.

display:
  logical resolution: 128x64 pixels
  orientation: landscape
  colors: monochrome
  optional desktop scale: --scale N

controls:
  D-pad = repeat the shown direction sequence
  A / Z / Enter = start / replay current cue sequence
  B / X / Escape = back / exit
  R = reset best round on title screen

gameplay:
  A direction sequence is shown one cue at a time.
  Repeat the sequence correctly to advance a round.
  Each new round appends one more direction.
  Wrong input ends the run.
  Best completed round persists beside this script.

DO NOT:
  Change the 128x64 logical coordinate system when porting to OLED.
  Couple this test module to the main HAPPY JARZ firmware yet.
============================================================
"""

import argparse
import random
import time
import tkinter as tk
from pathlib import Path

W = 128
H = 64
FPS_MS = 33
SAVE_PATH = Path(__file__).with_name("memory_spark_best.txt")
DIRS = ("UP", "RIGHT", "DOWN", "LEFT")


class MemorySpark:
    def __init__(self, root, scale=1):
        self.root = root
        self.scale = max(1, int(scale))
        self.canvas = tk.Canvas(root, width=W*self.scale, height=H*self.scale,
                                bg="black", highlightthickness=0, bd=0)
        self.canvas.pack()
        root.title("Memory Spark — 128x64 OLED Test")
        root.resizable(False, False)

        self.state = "title"
        self.best = self.load_best()
        self.sequence = []
        self.completed_rounds = 0
        self.input_index = 0
        self.show_index = 0
        self.show_phase = "off"
        self.show_timer = 0.0
        self.active_dir = None
        self.message = ""
        self.message_timer = 0.0
        self.flash_bad = 0.0
        self.last_time = time.perf_counter()

        self.bind_keys()
        self.loop()

    def load_best(self):
        try:
            return max(0, int(SAVE_PATH.read_text().strip()))
        except Exception:
            return 0

    def save_best(self):
        try:
            SAVE_PATH.write_text(str(self.best))
        except Exception:
            pass

    def bind_keys(self):
        self.root.bind("<KeyPress-Up>", lambda e: self.press_dir("UP"))
        self.root.bind("<KeyPress-Right>", lambda e: self.press_dir("RIGHT"))
        self.root.bind("<KeyPress-Down>", lambda e: self.press_dir("DOWN"))
        self.root.bind("<KeyPress-Left>", lambda e: self.press_dir("LEFT"))
        for key in ("a", "A", "z", "Z", "Return"):
            self.root.bind(f"<KeyPress-{key}>", self.press_a)
        for key in ("b", "B", "x", "X", "Escape"):
            self.root.bind(f"<KeyPress-{key}>", self.press_b)
        self.root.bind("<KeyPress-r>", self.reset_best)
        self.root.bind("<KeyPress-R>", self.reset_best)

    def press_a(self, event=None):
        if self.state == "title":
            self.start_game()
        elif self.state == "input":
            self.start_show_sequence()
        elif self.state == "gameover":
            self.start_game()

    def press_b(self, event=None):
        if self.state == "title":
            self.root.destroy()
        elif self.state == "gameover":
            self.state = "title"
        elif self.state in ("show", "input", "roundwin"):
            self.state = "title"
            self.active_dir = None

    def reset_best(self, event=None):
        if self.state == "title":
            self.best = 0
            self.save_best()

    def press_dir(self, direction):
        if self.state != "input":
            return
        self.active_dir = direction
        self.message_timer = 0.12

        if self.sequence[self.input_index] != direction:
            self.flash_bad = 0.45
            self.message = "MISS!"
            self.message_timer = 0.7
            self.end_game()
            return

        self.input_index += 1
        if self.input_index >= len(self.sequence):
            self.completed_rounds += 1
            if self.completed_rounds > self.best:
                self.best = self.completed_rounds
                self.save_best()
            self.state = "roundwin"
            self.message = "NICE!"
            self.message_timer = 0.8
            self.show_timer = 0.9

    def start_game(self):
        self.sequence = []
        self.completed_rounds = 0
        self.input_index = 0
        self.message = ""
        self.message_timer = 0.0
        self.flash_bad = 0.0
        self.next_round()

    def next_round(self):
        self.sequence.append(random.choice(DIRS))
        self.input_index = 0
        self.start_show_sequence()

    def start_show_sequence(self):
        self.state = "show"
        self.show_index = 0
        self.show_phase = "on"
        self.show_timer = self.cue_on_time()
        self.active_dir = self.sequence[0] if self.sequence else None

    def cue_on_time(self):
        return max(0.20, 0.48 - self.completed_rounds * 0.015)

    def cue_gap_time(self):
        return max(0.12, 0.25 - self.completed_rounds * 0.006)

    def end_game(self):
        self.state = "gameover"
        self.active_dir = None

    def update(self, dt):
        self.message_timer = max(0.0, self.message_timer - dt)
        self.flash_bad = max(0.0, self.flash_bad - dt)

        if self.state == "show":
            self.show_timer -= dt
            if self.show_timer <= 0:
                if self.show_phase == "on":
                    self.show_phase = "gap"
                    self.active_dir = None
                    self.show_timer = self.cue_gap_time()
                else:
                    self.show_index += 1
                    if self.show_index >= len(self.sequence):
                        self.state = "input"
                        self.input_index = 0
                        self.active_dir = None
                        self.message = "YOUR TURN"
                        self.message_timer = 0.7
                    else:
                        self.show_phase = "on"
                        self.active_dir = self.sequence[self.show_index]
                        self.show_timer = self.cue_on_time()

        elif self.state == "roundwin":
            self.show_timer -= dt
            if self.show_timer <= 0:
                self.next_round()

        if self.state == "input" and self.message_timer <= 0:
            self.active_dir = None

    def px_rect(self, x0, y0, x1, y1, fill="white", outline=None):
        s = self.scale
        self.canvas.create_rectangle(int(x0*s), int(y0*s),
                                     int((x1+1)*s-1), int((y1+1)*s-1),
                                     fill=fill,
                                     outline=outline if outline is not None else fill,
                                     width=max(1, self.scale))

    def line(self, x0, y0, x1, y1, fill="white"):
        s = self.scale
        self.canvas.create_line(int(x0*s), int(y0*s), int(x1*s), int(y1*s),
                                fill=fill, width=max(1, self.scale))

    def text(self, x, y, txt, anchor="nw", size=5):
        s = self.scale
        self.canvas.create_text(int(x*s), int(y*s), text=txt, fill="white",
                                anchor=anchor,
                                font=("TkFixedFont", max(4, size*s)))

    def draw_arrow(self, direction, active=False):
        centers = {"UP": (64,22), "RIGHT": (88,36), "DOWN": (64,50), "LEFT": (40,36)}
        cx, cy = centers[direction]
        if active:
            self.px_rect(cx-9, cy-8, cx+9, cy+8)
            color = "black"
        else:
            color = "white"

        if direction == "UP":
            pts = [(cx,cy-5),(cx-5,cy+1),(cx-2,cy+1),(cx-2,cy+5),(cx+2,cy+5),(cx+2,cy+1),(cx+5,cy+1)]
        elif direction == "DOWN":
            pts = [(cx,cy+5),(cx-5,cy-1),(cx-2,cy-1),(cx-2,cy-5),(cx+2,cy-5),(cx+2,cy-1),(cx+5,cy-1)]
        elif direction == "LEFT":
            pts = [(cx-5,cy),(cx+1,cy-5),(cx+1,cy-2),(cx+5,cy-2),(cx+5,cy+2),(cx+1,cy+2),(cx+1,cy+5)]
        else:
            pts = [(cx+5,cy),(cx-1,cy-5),(cx-1,cy-2),(cx-5,cy-2),(cx-5,cy+2),(cx-1,cy+2),(cx-1,cy+5)]
        s = self.scale
        self.canvas.create_polygon([(int(x*s), int(y*s)) for x,y in pts], fill=color, outline=color)

    def render_title(self):
        self.text(64, 8, "MEMORY", anchor="n", size=7)
        self.text(64, 20, "SPARK", anchor="n", size=7)
        self.text(64, 37, "A: PLAY", anchor="n", size=5)
        self.text(64, 46, f"BEST {self.best:02d}", anchor="n", size=5)
        self.text(64, 56, "B: EXIT", anchor="n", size=4)

    def render_game(self):
        self.text(1, 0, f"R{self.completed_rounds+1:02d}", size=5)
        self.text(127, 0, f"{self.input_index}/{len(self.sequence)}", anchor="ne", size=5)
        self.line(0, 8, 127, 8)
        for d in DIRS:
            self.draw_arrow(d, active=(self.active_dir == d))
        if self.state == "show":
            self.text(64, 10, "WATCH", anchor="n", size=4)
        elif self.state == "input":
            self.text(64, 10, "REPEAT", anchor="n", size=4)
        if self.message_timer > 0 and self.message:
            self.px_rect(38, 27, 90, 43, fill="black")
            self.text(64, 31, self.message, anchor="n", size=5)
        if self.flash_bad > 0:
            self.px_rect(0, 9, 2, 63)
            self.px_rect(125, 9, 127, 63)

    def render_gameover(self):
        self.text(64, 10, "SPARK LOST", anchor="n", size=6)
        self.text(64, 28, f"ROUND {self.completed_rounds:02d}", anchor="n", size=5)
        self.text(64, 38, f"BEST  {self.best:02d}", anchor="n", size=5)
        self.text(64, 51, "A AGAIN  B BACK", anchor="n", size=4)

    def render(self):
        self.canvas.delete("all")
        if self.state == "title":
            self.render_title()
        elif self.state == "gameover":
            self.render_gameover()
        else:
            self.render_game()

    def loop(self):
        now = time.perf_counter()
        dt = min(0.05, now-self.last_time)
        self.last_time = now
        self.update(dt)
        self.render()
        self.root.after(FPS_MS, self.loop)


def main():
    parser = argparse.ArgumentParser(description="HAPPY JARZ Memory Spark — 128x64 OLED test app")
    parser.add_argument("--scale", type=int, default=1)
    args = parser.parse_args()
    root = tk.Tk()
    MemorySpark(root, scale=args.scale)
    root.mainloop()


if __name__ == "__main__":
    main()
