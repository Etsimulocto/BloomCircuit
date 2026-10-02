#!/usr/bin/env python3
"""
============================================================
BLOOMCORE MODULE
============================================================
identity:
  name: HAPPY JARZ — Meteor Tap
  module: meteor_tap
  version: 0.1
  format: bloomcore/v1.3

purpose:
  Standalone 128x64 landscape monochrome OLED timing minigame.
  Move a target cursor between fixed slots and tap A when a falling
  spark crosses the timing line in the same slot.

display:
  logical resolution: 128x64 pixels
  orientation: landscape
  colors: monochrome
  optional desktop scale: --scale N

controls:
  LEFT / RIGHT = move cursor one fixed slot per touch
  A / Z / Enter = tap / start
  B / X / Escape = back / exit
  R = reset best score on title screen

gameplay:
  Sparks fall in one of 10 lanes.
  Move the cursor under the active lane and tap A as the spark crosses
  the target line.
  Good timing scores points and builds streak.
  Early / late / wrong-lane taps cost a life.
  Missing a spark also costs a life.
  Speed increases with streak and score.

storage:
  Best score saved beside this script as:
    meteor_tap_best.txt

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
HUD_H = 9
TARGET_Y = 50
SLOT_COUNT = 10
SLOT_LEFT = 8
SLOT_RIGHT = W - 9
SLOT_X = [
    SLOT_LEFT + i * (SLOT_RIGHT - SLOT_LEFT) / (SLOT_COUNT - 1)
    for i in range(SLOT_COUNT)
]
SAVE_PATH = Path(__file__).with_name("meteor_tap_best.txt")


class MeteorTap:
    def __init__(self, root, scale=1):
        self.root = root
        self.scale = max(1, int(scale))
        self.canvas = tk.Canvas(root, width=W*self.scale, height=H*self.scale,
                                bg="black", highlightthickness=0, bd=0)
        self.canvas.pack()
        root.title("Meteor Tap — 128x64 OLED Test")
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
        self.root.bind("<KeyPress-Left>", self.step_left)
        self.root.bind("<KeyPress-Right>", self.step_right)
        for key in ("a", "A", "z", "Z", "Return"):
            self.root.bind(f"<KeyPress-{key}>", self.press_a)
        for key in ("b", "B", "x", "X", "Escape"):
            self.root.bind(f"<KeyPress-{key}>", self.press_b)
        self.root.bind("<KeyPress-r>", self.reset_best)
        self.root.bind("<KeyPress-R>", self.reset_best)

    def reset_best(self, event=None):
        if self.state == "title":
            self.best = 0
            self.save_best()

    def reset_game(self):
        self.cursor_slot = 4
        self.spark_slot = 5
        self.spark_y = 12.0
        self.spark_speed = 16.0
        self.score = 0
        self.streak = 0
        self.lives = 3
        self.message = ""
        self.message_timer = 0.0
        self.flash_timer = 0.0
        self.wait_timer = 0.0
        self.active = False

    def start_game(self):
        self.reset_game()
        self.state = "play"
        self.spawn_spark()

    def step_left(self, event=None):
        if self.state == "play":
            self.cursor_slot = max(0, self.cursor_slot - 1)

    def step_right(self, event=None):
        if self.state == "play":
            self.cursor_slot = min(SLOT_COUNT - 1, self.cursor_slot + 1)

    def press_a(self, event=None):
        if self.state in ("title", "gameover"):
            self.start_game()
            return
        if self.state != "play" or not self.active:
            return

        lane_ok = self.cursor_slot == self.spark_slot
        dy = abs(self.spark_y - TARGET_Y)

        if lane_ok and dy <= 2.0:
            gain = 3
            label = "PERFECT"
        elif lane_ok and dy <= 5.0:
            gain = 2
            label = "NICE"
        elif lane_ok and dy <= 8.0:
            gain = 1
            label = "GOOD"
        else:
            self.lose_life("MISS")
            return

        self.score += gain
        self.streak += 1
        self.message = label
        self.message_timer = 0.45
        self.flash_timer = 0.10
        if self.score > self.best:
            self.best = self.score
            self.save_best()
        self.active = False
        self.wait_timer = 0.35

    def press_b(self, event=None):
        if self.state == "title":
            self.root.destroy()
        elif self.state == "gameover":
            self.state = "title"
        elif self.state == "play":
            self.state = "title"

    def spawn_spark(self):
        self.spark_slot = random.randrange(SLOT_COUNT)
        self.spark_y = HUD_H + 3
        self.spark_speed = min(38.0, 16.0 + self.score * 0.55 + self.streak * 0.65)
        self.active = True

    def lose_life(self, label):
        self.lives -= 1
        self.streak = 0
        self.message = label
        self.message_timer = 0.55
        self.flash_timer = 0.18
        self.active = False
        if self.lives <= 0:
            self.state = "gameover"
            if self.score > self.best:
                self.best = self.score
                self.save_best()
        else:
            self.wait_timer = 0.45

    def update(self, dt):
        self.message_timer = max(0.0, self.message_timer - dt)
        self.flash_timer = max(0.0, self.flash_timer - dt)

        if self.state != "play":
            return

        if self.active:
            self.spark_y += self.spark_speed * dt
            if self.spark_y > H + 2:
                self.lose_life("TOO LATE")
        else:
            self.wait_timer -= dt
            if self.wait_timer <= 0 and self.state == "play":
                self.spawn_spark()

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

    def draw_spark(self):
        if not self.active:
            return
        x = int(round(SLOT_X[self.spark_slot]))
        y = int(round(self.spark_y))
        self.line(x-2, y, x+2, y)
        self.line(x, y-2, x, y+2)
        self.px_rect(x-1, y-1, x-1, y-1)
        self.px_rect(x+1, y+1, x+1, y+1)

    def draw_cursor(self):
        x = int(round(SLOT_X[self.cursor_slot]))
        self.line(x-4, 60, x+4, 60)
        self.line(x-3, 59, x+3, 59)
        self.px_rect(x, 57, x, 58)

    def render_title(self):
        self.text(64, 8, "METEOR", anchor="n", size=7)
        self.text(64, 20, "TAP", anchor="n", size=7)
        self.text(64, 37, "A: PLAY", anchor="n", size=5)
        self.text(64, 46, f"BEST {self.best:03d}", anchor="n", size=5)
        self.text(64, 56, "B: EXIT", anchor="n", size=4)

    def render_game(self):
        self.text(1, 0, f"S{self.score:03d}", size=5)
        self.text(64, 0, f"x{self.streak:02d}", anchor="n", size=5)
        self.text(127, 0, "<3" * self.lives, anchor="ne", size=4)
        self.line(0, 8, 127, 8)

        for x in SLOT_X:
            xx = int(round(x))
            self.px_rect(xx, TARGET_Y, xx, TARGET_Y)
        self.line(0, TARGET_Y, 127, TARGET_Y)

        self.draw_spark()
        self.draw_cursor()

        if self.message_timer > 0 and self.message:
            self.px_rect(40, 27, 88, 39, fill="black")
            self.text(64, 29, self.message, anchor="n", size=5)

        if self.flash_timer > 0:
            self.px_rect(0, 9, 1, 63)
            self.px_rect(126, 9, 127, 63)

    def render_gameover(self):
        self.text(64, 10, "METEOR LOST", anchor="n", size=6)
        self.text(64, 28, f"SCORE {self.score:03d}", anchor="n", size=5)
        self.text(64, 38, f"BEST  {self.best:03d}", anchor="n", size=5)
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
        dt = min(0.05, now - self.last_time)
        self.last_time = now
        self.update(dt)
        self.render()
        self.root.after(FPS_MS, self.loop)


def main():
    parser = argparse.ArgumentParser(description="HAPPY JARZ Meteor Tap — 128x64 OLED test app")
    parser.add_argument("--scale", type=int, default=1)
    args = parser.parse_args()
    root = tk.Tk()
    MeteorTap(root, scale=args.scale)
    root.mainloop()


if __name__ == "__main__":
    main()
