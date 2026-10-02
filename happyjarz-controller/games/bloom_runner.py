#!/usr/bin/env python3
"""
============================================================
BLOOMCORE MODULE
============================================================
identity:
  name: HAPPY JARZ — Bloom Runner
  module: bloom_runner
  version: 0.1
  format: bloomcore/v1.3

purpose:
  Standalone 128x64 landscape monochrome OLED auto-runner.

display:
  logical resolution: 128x64 pixels
  orientation: landscape
  colors: monochrome
  optional desktop scale: --scale N

controls:
  LEFT / RIGHT = shift between 3 running lanes
  A / Z / Enter = jump
  B / X = duck / slide while playing
  Escape = back / exit
  R = reset best score on title

gameplay:
  Character runs automatically.
  Shift between three lanes to avoid lane hazards and collect glitter.
  Jump clears ground blocks.
  Duck clears overhead bars.
  Glitter gives bonus points.
  Difficulty increases over time.
  Best score persists beside this script.

DO NOT:
  Change the 128x64 logical coordinate system when porting to OLED.
  Couple this test module to the main HAPPY JARZ firmware yet.
============================================================
"""

import argparse
import random
import time
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path

W = 128
H = 64
FPS_MS = 33
HUD_H = 9
GROUND_Y = 58
LANE_Y = (26, 41, 56)
SAVE_PATH = Path(__file__).with_name("bloom_runner_best.txt")


@dataclass
class Thing:
    x: float
    lane: int
    kind: str  # block, bar, glitter
    passed: bool = False


class BloomRunner:
    def __init__(self, root, scale=1):
        self.root = root
        self.scale = max(1, int(scale))
        self.canvas = tk.Canvas(root, width=W*self.scale, height=H*self.scale,
                                bg="black", highlightthickness=0, bd=0)
        self.canvas.pack()
        root.title("Bloom Runner — 128x64 OLED Test")
        root.resizable(False, False)

        self.state = "title"
        self.best = self.load_best()
        self.last_time = time.perf_counter()
        self.bind_keys()
        self.reset_game()
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
        self.root.bind("<KeyPress-Left>", lambda e: self.shift(-1))
        self.root.bind("<KeyPress-Right>", lambda e: self.shift(1))
        for key in ("a", "A", "z", "Z", "Return"):
            self.root.bind(f"<KeyPress-{key}>", self.press_a)
        for key in ("b", "B", "x", "X"):
            self.root.bind(f"<KeyPress-{key}>", self.press_b)
            self.root.bind(f"<KeyRelease-{key}>", self.release_b)
        self.root.bind("<KeyPress-Escape>", self.press_escape)
        self.root.bind("<KeyPress-r>", self.reset_best)
        self.root.bind("<KeyPress-R>", self.reset_best)

    def reset_best(self, event=None):
        if self.state == "title":
            self.best = 0
            self.save_best()

    def reset_game(self):
        self.lane = 1
        self.score = 0.0
        self.glitter = 0
        self.objects = []
        self.spawn_timer = 1.0
        self.elapsed = 0.0
        self.jump_y = 0.0
        self.jump_v = 0.0
        self.ducking = False
        self.message = ""
        self.message_timer = 0.0

    def start_game(self):
        self.reset_game()
        self.state = "play"

    def shift(self, delta):
        if self.state == "play":
            self.lane = max(0, min(2, self.lane + delta))

    def press_a(self, event=None):
        if self.state in ("title", "gameover"):
            self.start_game()
        elif self.state == "play" and self.jump_y == 0:
            self.jump_v = -42.0

    def press_b(self, event=None):
        if self.state == "title":
            self.root.destroy()
        elif self.state == "gameover":
            self.state = "title"
        elif self.state == "play":
            self.ducking = True

    def release_b(self, event=None):
        if self.state == "play":
            self.ducking = False

    def press_escape(self, event=None):
        if self.state == "title":
            self.root.destroy()
        else:
            self.state = "title"

    def speed(self):
        return min(58.0, 22.0 + self.elapsed * 0.45)

    def spawn_one(self):
        lane = random.randrange(3)
        roll = random.random()
        if roll < 0.24:
            kind = "glitter"
        elif roll < 0.60:
            kind = "block"
        else:
            kind = "bar"
        self.objects.append(Thing(W + 4, lane, kind))

    def update(self, dt):
        if self.state != "play":
            return

        self.elapsed += dt
        self.score += dt * 4.0
        self.message_timer = max(0.0, self.message_timer - dt)

        if self.jump_y != 0 or self.jump_v != 0:
            self.jump_v += 90.0 * dt
            self.jump_y += self.jump_v * dt
            if self.jump_y >= 0:
                self.jump_y = 0
                self.jump_v = 0

        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            self.spawn_one()
            gap = max(0.52, 1.15 - self.elapsed * 0.008)
            self.spawn_timer = gap * random.uniform(0.8, 1.25)

        px = 20
        survivors = []
        for obj in self.objects:
            obj.x -= self.speed() * dt
            same_lane = obj.lane == self.lane
            near_player = 15 <= obj.x <= 28

            if same_lane and near_player and not obj.passed:
                if obj.kind == "glitter":
                    self.score += 10
                    self.glitter += 1
                    self.message = "+GLITTER"
                    self.message_timer = 0.35
                    obj.passed = True
                elif obj.kind == "block":
                    if self.jump_y > -5:
                        self.end_game()
                        return
                    obj.passed = True
                elif obj.kind == "bar":
                    if not self.ducking:
                        self.end_game()
                        return
                    obj.passed = True

            if obj.x > -8:
                survivors.append(obj)

        self.objects = survivors

    def end_game(self):
        self.state = "gameover"
        final = int(self.score)
        if final > self.best:
            self.best = final
            self.save_best()

    def px_rect(self, x0, y0, x1, y1, fill="white"):
        s = self.scale
        self.canvas.create_rectangle(int(x0*s), int(y0*s),
                                     int((x1+1)*s-1), int((y1+1)*s-1),
                                     fill=fill, outline=fill)

    def line(self, x0, y0, x1, y1, fill="white"):
        s = self.scale
        self.canvas.create_line(int(x0*s), int(y0*s), int(x1*s), int(y1*s),
                                fill=fill, width=max(1, self.scale))

    def text(self, x, y, txt, anchor="nw", size=5):
        s = self.scale
        self.canvas.create_text(int(x*s), int(y*s), text=txt, fill="white",
                                anchor=anchor,
                                font=("TkFixedFont", max(4, size*s)))

    def draw_runner(self):
        x = 20
        base_y = LANE_Y[self.lane] + int(self.jump_y)
        if self.ducking and self.jump_y == 0:
            self.px_rect(x-4, base_y-3, x+4, base_y)
            self.px_rect(x+3, base_y-5, x+5, base_y-2)
        else:
            self.px_rect(x-2, base_y-8, x+2, base_y-3)
            self.px_rect(x-1, base_y-12, x+2, base_y-9)
            self.line(x-1, base_y-2, x-4, base_y+2)
            self.line(x+1, base_y-2, x+4, base_y+2)

    def draw_object(self, obj):
        x = int(obj.x)
        y = LANE_Y[obj.lane]
        if obj.kind == "block":
            self.px_rect(x-3, y-5, x+3, y)
        elif obj.kind == "bar":
            self.px_rect(x-4, y-12, x+4, y-9)
            self.line(x-4, y-8, x-4, y)
            self.line(x+4, y-8, x+4, y)
        else:
            self.line(x-2, y-4, x+2, y-4)
            self.line(x, y-6, x, y-2)
            self.px_rect(x, y-4, x, y-4)

    def render_title(self):
        self.text(64, 8, "BLOOM RUNNER", anchor="n", size=7)
        self.text(64, 28, "A: PLAY", anchor="n", size=5)
        self.text(64, 39, f"BEST {self.best:04d}", anchor="n", size=5)
        self.text(64, 52, "B: EXIT", anchor="n", size=4)

    def render_game(self):
        self.text(1, 0, f"S{int(self.score):04d}", size=5)
        self.text(127, 0, f"G{self.glitter:02d}", anchor="ne", size=5)
        self.line(0, 8, 127, 8)
        for y in LANE_Y:
            self.line(0, y+2, 127, y+2)
        for obj in self.objects:
            self.draw_object(obj)
        self.draw_runner()
        if self.message_timer > 0:
            self.text(64, 10, self.message, anchor="n", size=4)

    def render_gameover(self):
        self.text(64, 9, "RUN OVER", anchor="n", size=7)
        self.text(64, 28, f"SCORE {int(self.score):04d}", anchor="n", size=5)
        self.text(64, 39, f"BEST  {self.best:04d}", anchor="n", size=5)
        self.text(64, 52, "A AGAIN  B BACK", anchor="n", size=4)

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
        dt = min(0.05, now - self.last_time)
        self.last_time = now
        self.update(dt)
        self.render()
        self.root.after(FPS_MS, self.loop)


def main():
    parser = argparse.ArgumentParser(description="HAPPY JARZ Bloom Runner — 128x64 OLED test app")
    parser.add_argument("--scale", type=int, default=1)
    args = parser.parse_args()
    root = tk.Tk()
    BloomRunner(root, scale=args.scale)
    root.mainloop()


if __name__ == "__main__":
    main()
