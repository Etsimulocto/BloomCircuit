#!/usr/bin/env python3
"""
============================================================
BLOOMCORE MODULE
============================================================
identity:
  name: HAPPY JARZ — Catch the Glitter
  module: catch_the_glitter
  version: 0.2
  format: bloomcore/v1.3

purpose:
  Standalone desktop test app for the HAPPY JARZ 128x64
  landscape monochrome OLED minigame.

display:
  logical resolution: 128x64 pixels
  orientation: landscape
  colors: monochrome (black / white)
  default desktop scale: 1x (window content is exactly 128x64)
  optional scale: --scale N

controls:
  LEFT / RIGHT  = one discrete catcher-slot step per touch/tap
  A key or Z    = A button / magnet
  B key or X    = B button / wide catcher
  ENTER         = A button
  ESCAPE        = B button / quit from title/game-over
  R             = reset high score (title screen)

gameplay:
  Catcher moves across 10 fixed horizontal slots.
  There is no per-pixel/analog horizontal movement.
  Catch falling glitter for points.
  Normal sparkle = +1
  Big sparkle    = +3
  Heart          = +1 life (max 3)
  X chunk        = lose 1 life
  Missed normal glitter does not cost a life.
  Difficulty increases every 10 catches.

abilities:
  A / MAGNET:
    Pull nearby catchable glitter toward the jar for ~1.3 sec.
    Recharges after 10 successful catches.

  B / WIDE JAR:
    Widens the catcher for ~2 sec.
    Recharges after 14 successful catches.

storage:
  High score saved beside this script as:
    catch_the_glitter_highscore.txt

diagnostics:
  Exact native OLED-sized test:
    python3 catch_the_glitter.py --scale 1
  Easier desktop viewing:
    python3 catch_the_glitter.py --scale 6

DO NOT:
  Change the 128x64 logical coordinate system when porting to OLED.
  Treat desktop scaling as gameplay resolution.
  Couple this test module to the main HAPPY JARZ firmware yet.
============================================================
"""

import argparse
import math
import random
import time
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path

W = 128
H = 64
HUD_H = 9
FPS_MS = 33  # ~30 FPS

# Touch-friendly catcher movement.
# Ten fixed lane centers, leaving enough edge clearance even for WIDE JAR.
SLOT_COUNT = 10
SLOT_LEFT = 13
SLOT_RIGHT = W - 13
SLOT_X = [
    SLOT_LEFT + i * (SLOT_RIGHT - SLOT_LEFT) / (SLOT_COUNT - 1)
    for i in range(SLOT_COUNT)
]

SAVE_PATH = Path(__file__).with_name("catch_the_glitter_highscore.txt")


@dataclass
class Glitter:
    x: float
    y: float
    vx: float
    vy: float
    kind: str
    phase: float
    age: float = 0.0


class CatchTheGlitter:
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
        root.title("Catch the Glitter — 128x64 OLED Test")
        root.resizable(False, False)

        self.state = "title"
        self.high_score = self.load_high_score()

        self.bind_keys()
        self.reset_game()
        self.last_time = time.perf_counter()
        self.loop()

    # -------------------------
    # Storage
    # -------------------------
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

    # -------------------------
    # Input
    # -------------------------
    def bind_keys(self):
        self.root.bind("<KeyPress-Left>", self.step_left)
        self.root.bind("<KeyPress-Right>", self.step_right)

        for key in ("a", "A", "z", "Z", "Return"):
            self.root.bind(f"<KeyPress-{key}>", self.press_a)

        for key in ("b", "B", "x", "X", "Escape"):
            self.root.bind(f"<KeyPress-{key}>", self.press_b)

        self.root.bind("<KeyPress-r>", self.reset_high_score)
        self.root.bind("<KeyPress-R>", self.reset_high_score)

    def step_left(self, event=None):
        if self.state == "play":
            self.player_slot = max(0, self.player_slot - 1)
            self.player_x = SLOT_X[self.player_slot]

    def step_right(self, event=None):
        if self.state == "play":
            self.player_slot = min(SLOT_COUNT - 1, self.player_slot + 1)
            self.player_x = SLOT_X[self.player_slot]

    def press_a(self, event=None):
        if self.state in ("title", "gameover"):
            self.start_game()
            return
        if self.state == "play" and self.magnet_ready:
            self.magnet_timer = 1.3
            self.magnet_ready = False
            self.magnet_charge = 0

    def press_b(self, event=None):
        if self.state == "title":
            self.root.destroy()
            return
        if self.state == "gameover":
            self.state = "title"
            return
        if self.state == "play" and self.wide_ready:
            self.wide_timer = 2.0
            self.wide_ready = False
            self.wide_charge = 0

    def reset_high_score(self, event=None):
        if self.state == "title":
            self.high_score = 0
            self.save_high_score()

    # -------------------------
    # Game state
    # -------------------------
    def reset_game(self):
        self.score = 0
        self.catches = 0
        self.lives = 3
        self.player_slot = (SLOT_COUNT - 1) // 2
        self.player_x = SLOT_X[self.player_slot]
        self.glitter = []
        self.spawn_timer = 0.25

        self.magnet_timer = 0.0
        self.wide_timer = 0.0
        self.magnet_charge = 10
        self.wide_charge = 14
        self.magnet_ready = True
        self.wide_ready = True

        self.storm_timer = 0.0
        self.storm_cooldown = random.uniform(18, 28)
        self.flash_timer = 0.0
        self.message = ""
        self.message_timer = 0.0

    def start_game(self):
        self.reset_game()
        self.state = "play"

    # -------------------------
    # Spawning / difficulty
    # -------------------------
    def difficulty(self):
        return min(8, self.catches // 10)

    def spawn_one(self):
        d = self.difficulty()

        roll = random.random()
        if roll < 0.06:
            kind = "heart"
        elif roll < 0.15 + d * 0.01:
            kind = "bad"
        elif roll < 0.28:
            kind = "big"
        else:
            kind = "normal"

        x = random.uniform(4, W - 5)
        y = HUD_H + 1
        drift = random.uniform(-5.0, 5.0) * (1 + d * 0.08)
        fall = random.uniform(10.0, 15.0) + d * 1.2

        if self.storm_timer > 0:
            fall *= random.uniform(1.0, 1.35)
            drift *= 1.35

        self.glitter.append(
            Glitter(
                x=x,
                y=y,
                vx=drift,
                vy=fall,
                kind=kind,
                phase=random.random() * math.tau,
            )
        )

    # -------------------------
    # Update
    # -------------------------
    def update(self, dt):
        if self.state != "play":
            return

        # Touch-friendly discrete movement.
        width = 24 if self.wide_timer > 0 else 13
        self.player_x = SLOT_X[self.player_slot]

        self.magnet_timer = max(0.0, self.magnet_timer - dt)
        self.wide_timer = max(0.0, self.wide_timer - dt)
        self.flash_timer = max(0.0, self.flash_timer - dt)
        self.message_timer = max(0.0, self.message_timer - dt)

        self.storm_cooldown -= dt
        if self.storm_timer > 0:
            self.storm_timer -= dt
        elif self.storm_cooldown <= 0:
            self.storm_timer = 4.5
            self.storm_cooldown = random.uniform(22, 34)
            self.message = "GLITTER STORM!"
            self.message_timer = 1.0

        d = self.difficulty()
        base_interval = max(0.18, 0.62 - d * 0.045)
        if self.storm_timer > 0:
            base_interval *= 0.40

        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            count = 1
            if self.storm_timer > 0 and random.random() < 0.32:
                count = random.randint(2, 3)
            for _ in range(count):
                self.spawn_one()
            self.spawn_timer = base_interval * random.uniform(0.70, 1.25)

        catcher_y = 56
        catcher_h = 5
        catcher_half = width / 2

        survivors = []
        for g in self.glitter:
            g.age += dt

            wobble = math.sin(g.age * 4.0 + g.phase) * (2.2 + d * 0.15)
            g.x += (g.vx + wobble) * dt
            g.y += g.vy * dt

            if g.x < 2:
                g.x = 2
                g.vx = abs(g.vx)
            elif g.x > W - 3:
                g.x = W - 3
                g.vx = -abs(g.vx)

            if self.magnet_timer > 0 and g.kind != "bad":
                dx = self.player_x - g.x
                dy = catcher_y - g.y
                dist2 = dx * dx + dy * dy
                if dist2 < 46 * 46 and g.y > 18:
                    g.x += dx * min(1.0, dt * 2.9)
                    g.y += max(0, dy) * min(0.45, dt * 1.1)

            caught = (
                g.y >= catcher_y - 2
                and g.y <= catcher_y + catcher_h + 3
                and abs(g.x - self.player_x) <= catcher_half + 2
            )

            if caught:
                self.handle_catch(g)
                continue

            if g.y > H + 4:
                continue

            survivors.append(g)

        self.glitter = survivors

    def handle_catch(self, g):
        self.flash_timer = 0.08

        if g.kind == "bad":
            self.lives -= 1
            self.message = "OUCH!"
            self.message_timer = 0.45
            if self.lives <= 0:
                self.end_game()
            return

        if g.kind == "heart":
            self.lives = min(3, self.lives + 1)
            self.score += 5
            self.catches += 1
        elif g.kind == "big":
            self.score += 3
            self.catches += 1
        else:
            self.score += 1
            self.catches += 1

        if not self.magnet_ready:
            self.magnet_charge += 1
            if self.magnet_charge >= 10:
                self.magnet_ready = True
                self.message = "MAGNET READY"
                self.message_timer = 0.7

        if not self.wide_ready:
            self.wide_charge += 1
            if self.wide_charge >= 14:
                self.wide_ready = True
                self.message = "WIDE READY"
                self.message_timer = 0.7

    def end_game(self):
        self.state = "gameover"
        if self.score > self.high_score:
            self.high_score = self.score
            self.save_high_score()

    # -------------------------
    # Rendering helpers
    # -------------------------
    def px_rect(self, x0, y0, x1, y1, fill="white"):
        s = self.scale
        self.canvas.create_rectangle(
            int(x0 * s),
            int(y0 * s),
            int((x1 + 1) * s - 1),
            int((y1 + 1) * s - 1),
            fill=fill,
            outline=fill,
        )

    def line(self, x0, y0, x1, y1, fill="white"):
        s = self.scale
        self.canvas.create_line(
            int(x0 * s),
            int(y0 * s),
            int(x1 * s),
            int(y1 * s),
            fill=fill,
            width=max(1, self.scale),
        )

    def text(self, x, y, txt, anchor="nw", size=5):
        # Tk font is only for desktop preview. Coordinates remain OLED-native.
        s = self.scale
        font_px = max(4, size * s)
        self.canvas.create_text(
            int(x * s),
            int(y * s),
            text=txt,
            fill="white",
            anchor=anchor,
            font=("TkFixedFont", max(4, font_px)),
        )

    def draw_heart(self, x, y):
        pts = [
            (x-2,y-1),(x-1,y-2),(x,y-1),(x+1,y-2),(x+2,y-1),
            (x-2,y),(x-1,y+1),(x,y+2),(x+1,y+1),(x+2,y),
            (x,y+1)
        ]
        for px, py in pts:
            self.px_rect(px, py, px, py)

    def draw_glitter(self, g):
        x, y = int(round(g.x)), int(round(g.y))
        twinkle = int(g.age * 10) % 2 == 0

        if g.kind == "normal":
            if twinkle:
                self.line(x - 2, y, x + 2, y)
                self.line(x, y - 2, x, y + 2)
            else:
                self.px_rect(x, y, x, y)
                self.px_rect(x-1, y-1, x-1, y-1)
                self.px_rect(x+1, y+1, x+1, y+1)

        elif g.kind == "big":
            self.line(x - 3, y, x + 3, y)
            self.line(x, y - 3, x, y + 3)
            self.px_rect(x-1, y-1, x-1, y-1)
            self.px_rect(x+1, y-1, x+1, y-1)
            self.px_rect(x-1, y+1, x-1, y+1)
            self.px_rect(x+1, y+1, x+1, y+1)

        elif g.kind == "heart":
            self.draw_heart(x, y)

        elif g.kind == "bad":
            self.line(x - 2, y - 2, x + 2, y + 2)
            self.line(x + 2, y - 2, x - 2, y + 2)

    def draw_catcher(self):
        width = 24 if self.wide_timer > 0 else 13
        cx = int(round(self.player_x))
        left = int(cx - width / 2)
        right = int(cx + width / 2)

        self.line(left, 55, left + 2, 60)
        self.line(left + 2, 60, right - 2, 60)
        self.line(right - 2, 60, right, 55)
        self.line(left, 55, right, 55)

        if self.magnet_timer > 0:
            self.px_rect(cx - 1, 52, cx + 1, 52)
            self.px_rect(cx - 4, 50, cx - 4, 50)
            self.px_rect(cx + 4, 50, cx + 4, 50)

    # -------------------------
    # Screens
    # -------------------------
    def render_title(self):
        self.text(64, 7, "CATCH THE", anchor="n", size=6)
        self.text(64, 18, "GLITTER", anchor="n", size=7)

        for x, y in [(12, 16), (21, 34), (106, 13), (113, 36), (94, 30)]:
            self.line(x-1, y, x+1, y)
            self.line(x, y-1, x, y+1)

        self.text(64, 38, "A: PLAY", anchor="n", size=5)
        self.text(64, 47, f"BEST {self.high_score:03d}", anchor="n", size=5)
        self.text(64, 56, "B: EXIT", anchor="n", size=4)

    def render_hud(self):
        self.text(1, 0, f"{self.score:03d}", size=5)

        for i in range(self.lives):
            self.draw_heart(36 + i * 7, 4)

        a = "A*" if self.magnet_ready else "A."
        b = "B*" if self.wide_ready else "B."
        self.text(92, 0, f"{a} {b}", size=5)

        self.line(0, HUD_H - 1, W - 1, HUD_H - 1)

    def render_play(self):
        self.render_hud()

        for g in self.glitter:
            self.draw_glitter(g)

        # Test-build lane ticks: ten 1-pixel markers show snap positions.
        for sx in SLOT_X:
            self.px_rect(int(round(sx)), 63, int(round(sx)), 63)

        self.draw_catcher()

        if self.message_timer > 0:
            s = self.scale
            self.canvas.create_rectangle(
                17*s, 24*s, 111*s, 34*s,
                fill="black", outline="black"
            )
            self.text(64, 25, self.message, anchor="n", size=5)

        if self.flash_timer > 0:
            self.px_rect(0, HUD_H, 2, HUD_H + 2)
            self.px_rect(W - 3, HUD_H, W - 1, HUD_H + 2)

    def render_gameover(self):
        self.text(64, 9, "GAME OVER", anchor="n", size=7)
        self.text(64, 27, f"SCORE {self.score:03d}", anchor="n", size=5)
        self.text(64, 37, f"BEST  {self.high_score:03d}", anchor="n", size=5)
        self.text(64, 50, "A AGAIN  B BACK", anchor="n", size=4)

    def render(self):
        self.canvas.delete("all")

        if self.state == "title":
            self.render_title()
        elif self.state == "play":
            self.render_play()
        elif self.state == "gameover":
            self.render_gameover()

    # -------------------------
    # Main loop
    # -------------------------
    def loop(self):
        now = time.perf_counter()
        dt = min(0.05, now - self.last_time)
        self.last_time = now

        self.update(dt)
        self.render()

        self.root.after(FPS_MS, self.loop)


def main():
    parser = argparse.ArgumentParser(
        description="HAPPY JARZ Catch the Glitter — exact 128x64 OLED-layout test app"
    )
    parser.add_argument(
        "--scale",
        type=int,
        default=1,
        help="integer desktop magnification; logical resolution always remains 128x64",
    )
    args = parser.parse_args()

    root = tk.Tk()
    CatchTheGlitter(root, scale=args.scale)
    root.mainloop()


if __name__ == "__main__":
    main()
