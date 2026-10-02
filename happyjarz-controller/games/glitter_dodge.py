#!/usr/bin/env python3
"""
============================================================
BLOOMCORE MODULE
============================================================
identity:
  name: HAPPY JARZ — Glitter Dodge
  module: glitter_dodge
  version: 0.1
  format: bloomcore/v1.3

purpose:
  Standalone 128x64 landscape monochrome OLED minigame.
  The player snaps between 10 fixed touch-friendly slots and
  avoids falling junk for as long as possible.

display:
  logical resolution: 128x64 pixels
  orientation: landscape
  colors: monochrome
  desktop scale: --scale N (visual only; gameplay remains 128x64)

controls:
  LEFT / RIGHT  = one fixed slot per tap
  A / Z / ENTER = SHIELD when charged
  B / X         = DASH two slots in held/last direction when charged
  ESCAPE        = back/exit
  R             = reset high score from title

gameplay:
  Survive falling junk.
  Score increases with survival time and near-misses.
  Collision costs one heart.
  Three hearts total.
  Difficulty rises over time.
  Occasional debris storms create dense patterns.

abilities:
  SHIELD:
    Negates one collision during a short active window.
    Recharges automatically over time.

  DASH:
    Jumps two slots quickly in the last movement direction.
    Recharges automatically over time.

storage:
  glitter_dodge_highscore.txt beside this script.

DO NOT:
  Change the 128x64 logical coordinate system when porting to OLED.
  Replace the 10-slot movement with analog/pixel movement.
  Couple this test app into the proven controller firmware yet.
============================================================
"""

import argparse
import math
import random
import time
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path

W, H = 128, 64
HUD_H = 9
FPS_MS = 33

SLOT_COUNT = 10
SLOT_LEFT = 8
SLOT_RIGHT = W - 9
SLOT_X = [
    SLOT_LEFT + i * (SLOT_RIGHT - SLOT_LEFT) / (SLOT_COUNT - 1)
    for i in range(SLOT_COUNT)
]

SAVE_PATH = Path(__file__).with_name("glitter_dodge_highscore.txt")


@dataclass
class Junk:
    x: float
    y: float
    vx: float
    vy: float
    kind: str
    phase: float
    age: float = 0.0
    grazed: bool = False


class GlitterDodge:
    def __init__(self, root, scale=1):
        self.root = root
        self.scale = max(1, int(scale))
        self.canvas = tk.Canvas(
            root,
            width=W * self.scale,
            height=H * self.scale,
            bg="black",
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack()
        self.root.title("Glitter Dodge — 128x64 OLED Test")
        self.root.resizable(False, False)

        self.state = "title"
        self.high_score = self.load_high_score()
        self.last_time = time.perf_counter()

        self.bind_keys()
        self.reset_game()
        self.loop()

    def load_high_score(self):
        try:
            return max(0, int(SAVE_PATH.read_text().strip()))
        except Exception:
            return 0

    def save_high_score(self):
        try:
            SAVE_PATH.write_text(str(self.high_score))
        except Exception:
            pass

    def bind_keys(self):
        self.root.bind("<KeyPress-Left>", self.step_left)
        self.root.bind("<KeyPress-Right>", self.step_right)

        for key in ("a", "A", "z", "Z", "Return"):
            self.root.bind(f"<KeyPress-{key}>", self.press_a)

        for key in ("b", "B", "x", "X"):
            self.root.bind(f"<KeyPress-{key}>", self.press_b)

        self.root.bind("<KeyPress-Escape>", self.press_escape)
        self.root.bind("<KeyPress-r>", self.reset_high_score)
        self.root.bind("<KeyPress-R>", self.reset_high_score)

    def step_left(self, event=None):
        if self.state == "play":
            self.last_dir = -1
            self.player_slot = max(0, self.player_slot - 1)

    def step_right(self, event=None):
        if self.state == "play":
            self.last_dir = 1
            self.player_slot = min(SLOT_COUNT - 1, self.player_slot + 1)

    def press_a(self, event=None):
        if self.state in ("title", "gameover"):
            self.start_game()
            return
        if self.state == "play" and self.shield_ready:
            self.shield_timer = 1.35
            self.shield_ready = False
            self.shield_charge = 0.0

    def press_b(self, event=None):
        if self.state == "title":
            self.root.destroy()
            return
        if self.state == "gameover":
            self.state = "title"
            return
        if self.state == "play" and self.dash_ready:
            self.player_slot = max(
                0, min(SLOT_COUNT - 1, self.player_slot + 2 * self.last_dir)
            )
            self.dash_ready = False
            self.dash_charge = 0.0
            self.message = "DASH!"
            self.message_timer = 0.25

    def press_escape(self, event=None):
        if self.state == "play":
            self.state = "title"
        else:
            self.root.destroy()

    def reset_high_score(self, event=None):
        if self.state == "title":
            self.high_score = 0
            self.save_high_score()

    def reset_game(self):
        self.player_slot = (SLOT_COUNT - 1) // 2
        self.last_dir = 1
        self.lives = 3

        self.score_float = 0.0
        self.score = 0
        self.elapsed = 0.0
        self.junk = []
        self.spawn_timer = 0.35

        self.invuln_timer = 0.0
        self.shield_timer = 0.0
        self.shield_charge = 7.0
        self.shield_ready = True
        self.dash_charge = 5.0
        self.dash_ready = True

        self.message = ""
        self.message_timer = 0.0
        self.storm_timer = 0.0
        self.storm_cooldown = random.uniform(15, 22)

    def start_game(self):
        self.reset_game()
        self.state = "play"

    def difficulty(self):
        return min(10, int(self.elapsed // 12))

    def spawn_one(self):
        d = self.difficulty()
        kind_roll = random.random()

        if kind_roll < 0.12:
            kind = "big"
        elif kind_roll < 0.26:
            kind = "shard"
        else:
            kind = "junk"

        x = random.uniform(4, W - 5)
        vy = random.uniform(12.0, 17.0) + d * 1.4
        vx = random.uniform(-4.0, 4.0) * (1 + 0.08 * d)

        if self.storm_timer > 0:
            vy *= random.uniform(1.0, 1.30)
            vx *= 1.4

        self.junk.append(
            Junk(
                x=x,
                y=HUD_H + 1,
                vx=vx,
                vy=vy,
                kind=kind,
                phase=random.random() * math.tau,
            )
        )

    def player_x(self):
        return SLOT_X[self.player_slot]

    def update(self, dt):
        if self.state != "play":
            return

        self.elapsed += dt
        self.score_float += dt * (10 + self.difficulty() * 1.5)
        self.score = int(self.score_float)

        self.invuln_timer = max(0.0, self.invuln_timer - dt)
        self.shield_timer = max(0.0, self.shield_timer - dt)
        self.message_timer = max(0.0, self.message_timer - dt)

        if not self.shield_ready:
            self.shield_charge += dt
            if self.shield_charge >= 7.0:
                self.shield_ready = True
                self.message = "SHIELD READY"
                self.message_timer = 0.65

        if not self.dash_ready:
            self.dash_charge += dt
            if self.dash_charge >= 5.0:
                self.dash_ready = True
                self.message = "DASH READY"
                self.message_timer = 0.65

        self.storm_cooldown -= dt
        if self.storm_timer > 0:
            self.storm_timer -= dt
        elif self.storm_cooldown <= 0:
            self.storm_timer = 4.2
            self.storm_cooldown = random.uniform(20, 30)
            self.message = "DEBRIS STORM!"
            self.message_timer = 0.9

        d = self.difficulty()
        interval = max(0.16, 0.58 - d * 0.035)
        if self.storm_timer > 0:
            interval *= 0.43

        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            count = 1
            if self.storm_timer > 0 and random.random() < 0.40:
                count = random.randint(2, 3)
            for _ in range(count):
                self.spawn_one()
            self.spawn_timer = interval * random.uniform(0.72, 1.22)

        px = self.player_x()
        survivors = []

        for j in self.junk:
            j.age += dt
            wobble = math.sin(j.age * 4.8 + j.phase) * (1.2 + d * 0.12)
            j.x += (j.vx + wobble) * dt
            j.y += j.vy * dt

            if j.x < 2:
                j.x = 2
                j.vx = abs(j.vx)
            elif j.x > W - 3:
                j.x = W - 3
                j.vx = -abs(j.vx)

            if not j.grazed and 49 <= j.y <= 58 and 5 < abs(j.x - px) <= 11:
                j.grazed = True
                self.score_float += 8
                self.message = "+GRAZE"
                self.message_timer = 0.18

            hitbox = 4 if j.kind == "big" else 3
            collided = 52 <= j.y <= 61 and abs(j.x - px) <= hitbox + 3

            if collided and self.invuln_timer <= 0:
                if self.shield_timer > 0:
                    self.shield_timer = 0.0
                    self.invuln_timer = 0.35
                    self.message = "BLOCK!"
                    self.message_timer = 0.35
                    continue

                self.lives -= 1
                self.invuln_timer = 0.9
                self.message = "HIT!"
                self.message_timer = 0.45
                if self.lives <= 0:
                    self.end_game()
                    return
                continue

            if j.y <= H + 5:
                survivors.append(j)

        self.junk = survivors

    def end_game(self):
        self.state = "gameover"
        if self.score > self.high_score:
            self.high_score = self.score
            self.save_high_score()

    def px_rect(self, x0, y0, x1, y1, fill="white"):
        s = self.scale
        self.canvas.create_rectangle(
            int(x0 * s), int(y0 * s),
            int((x1 + 1) * s - 1), int((y1 + 1) * s - 1),
            fill=fill, outline=fill
        )

    def line(self, x0, y0, x1, y1, fill="white"):
        s = self.scale
        self.canvas.create_line(
            int(x0 * s), int(y0 * s),
            int(x1 * s), int(y1 * s),
            fill=fill, width=max(1, self.scale)
        )

    def text(self, x, y, txt, anchor="nw", size=5):
        s = self.scale
        self.canvas.create_text(
            int(x * s), int(y * s),
            text=txt, fill="white", anchor=anchor,
            font=("TkFixedFont", max(4, size * s))
        )

    def draw_heart(self, x, y):
        pts = [
            (x-2,y-1),(x-1,y-2),(x,y-1),(x+1,y-2),(x+2,y-1),
            (x-2,y),(x-1,y+1),(x,y+2),(x+1,y+1),(x+2,y),(x,y+1)
        ]
        for px, py in pts:
            self.px_rect(px, py, px, py)

    def draw_junk(self, j):
        x, y = int(round(j.x)), int(round(j.y))
        if j.kind == "junk":
            self.line(x-2, y-2, x+2, y+2)
            self.line(x+2, y-2, x-2, y+2)
            self.px_rect(x, y, x, y)
        elif j.kind == "shard":
            self.line(x, y-3, x+2, y)
            self.line(x+2, y, x-1, y+3)
            self.line(x-1, y+3, x, y-3)
        else:
            self.line(x-3, y-3, x+3, y+3)
            self.line(x+3, y-3, x-3, y+3)
            self.line(x-3, y, x+3, y)
            self.line(x, y-3, x, y+3)

    def draw_player(self):
        x = int(round(self.player_x()))

        if self.invuln_timer > 0 and int(self.invuln_timer * 14) % 2 == 0:
            return

        self.line(x-3, 54, x+3, 54)
        self.line(x-2, 55, x-2, 60)
        self.line(x+2, 55, x+2, 60)
        self.line(x-2, 60, x+2, 60)
        self.px_rect(x, 56, x, 57)

        if self.shield_timer > 0:
            self.line(x-6, 52, x-7, 56)
            self.line(x-7, 56, x-6, 61)
            self.line(x+6, 52, x+7, 56)
            self.line(x+7, 56, x+6, 61)

    def render_hud(self):
        self.text(1, 0, f"{self.score:04d}", size=5)
        for i in range(self.lives):
            self.draw_heart(41 + i * 7, 4)

        a = "A*" if self.shield_ready else "A."
        b = "B*" if self.dash_ready else "B."
        self.text(92, 0, f"{a} {b}", size=5)
        self.line(0, HUD_H - 1, W - 1, HUD_H - 1)

    def render_title(self):
        self.text(64, 7, "GLITTER", anchor="n", size=7)
        self.text(64, 18, "DODGE", anchor="n", size=7)

        for x, y in [(13,18),(23,35),(104,14),(115,32),(94,40)]:
            self.line(x-1, y-1, x+1, y+1)
            self.line(x+1, y-1, x-1, y+1)

        self.text(64, 38, "A: PLAY", anchor="n", size=5)
        self.text(64, 47, f"BEST {self.high_score:04d}", anchor="n", size=5)
        self.text(64, 56, "B: EXIT", anchor="n", size=4)

    def render_play(self):
        self.render_hud()

        for sx in SLOT_X:
            self.px_rect(int(round(sx)), 63, int(round(sx)), 63)

        for j in self.junk:
            self.draw_junk(j)

        self.draw_player()

        if self.message_timer > 0:
            s = self.scale
            self.canvas.create_rectangle(
                20*s, 25*s, 108*s, 34*s,
                fill="black", outline="black"
            )
            self.text(64, 25, self.message, anchor="n", size=5)

    def render_gameover(self):
        self.text(64, 9, "GAME OVER", anchor="n", size=7)
        self.text(64, 27, f"SCORE {self.score:04d}", anchor="n", size=5)
        self.text(64, 37, f"BEST  {self.high_score:04d}", anchor="n", size=5)
        self.text(64, 50, "A AGAIN  B BACK", anchor="n", size=4)

    def render(self):
        self.canvas.delete("all")
        if self.state == "title":
            self.render_title()
        elif self.state == "play":
            self.render_play()
        else:
            self.render_gameover()

    def loop(self):
        now = time.perf_counter()
        dt = min(0.05, now - self.last_time)
        self.last_time = now
        self.update(dt)
        self.render()
        self.root.after(FPS_MS, self.loop)


def main():
    parser = argparse.ArgumentParser(
        description="HAPPY JARZ Glitter Dodge — exact 128x64 OLED-layout test app"
    )
    parser.add_argument(
        "--scale",
        type=int,
        default=1,
        help="desktop magnification only; logical game resolution remains 128x64",
    )
    args = parser.parse_args()

    root = tk.Tk()
    GlitterDodge(root, scale=args.scale)
    root.mainloop()


if __name__ == "__main__":
    main()
