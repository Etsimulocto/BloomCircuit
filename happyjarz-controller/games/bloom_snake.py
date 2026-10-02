#!/usr/bin/env python3
"""
============================================================
BLOOMCORE MODULE
============================================================
identity:
  name: HAPPY JARZ — Bloom Snake
  module: bloom_snake
  version: 0.1
  format: bloomcore/v1.3

purpose:
  Standalone 128x64 landscape monochrome minigame for the
  HAPPY JARZ OLED arcade.

display:
  logical resolution: 128x64 pixels
  orientation: landscape
  colors: monochrome
  play grid: 16 columns x 7 rows, 8x8 pixels per cell
  HUD: top 8 pixels

controls:
  D-PAD = turn snake
  A / Z / ENTER = start or activate slow-mo when charged
  B / X / ESCAPE = back / exit from title or game-over

rules:
  Snake moves automatically.
  Eat glitter to grow and score.
  Screen edges wrap instead of killing the player.
  Hitting your own body ends the run.
  Speed increases gradually as score rises.

ability:
  A / SLOW BLOOM:
    Slows movement for about 3 seconds.
    Recharges after eating 5 glitter pieces.

storage:
  High score saved beside this script as:
    bloom_snake_highscore.txt

DO NOT:
  Change the 128x64 logical coordinate system when porting.
  Couple this module to the main HAPPY JARZ firmware yet.
============================================================
"""

import argparse
import random
import time
import tkinter as tk
from pathlib import Path

W = 128
H = 64
HUD_H = 8
CELL = 8
COLS = 16
ROWS = 7
FPS_MS = 16
SAVE_PATH = Path(__file__).with_name("bloom_snake_highscore.txt")

DIRS = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}
OPPOSITE = {
    "up": "down",
    "down": "up",
    "left": "right",
    "right": "left",
}


class BloomSnake:
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
        root.title("Bloom Snake — 128x64 OLED Test")
        root.resizable(False, False)

        self.high_score = self.load_high_score()
        self.state = "title"
        self.bind_keys()
        self.reset_game()
        self.last_time = time.perf_counter()
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
        self.root.bind("<KeyPress-Up>", lambda e: self.turn("up"))
        self.root.bind("<KeyPress-Down>", lambda e: self.turn("down"))
        self.root.bind("<KeyPress-Left>", lambda e: self.turn("left"))
        self.root.bind("<KeyPress-Right>", lambda e: self.turn("right"))

        for key in ("a", "A", "z", "Z", "Return"):
            self.root.bind(f"<KeyPress-{key}>", self.press_a)
        for key in ("b", "B", "x", "X", "Escape"):
            self.root.bind(f"<KeyPress-{key}>", self.press_b)

    def reset_game(self):
        self.score = 0
        self.snake = [(7, 3), (6, 3), (5, 3)]
        self.direction = "right"
        self.pending_direction = "right"
        self.food = None
        self.move_timer = 0.0
        self.slow_timer = 0.0
        self.slow_charge = 5
        self.slow_ready = True
        self.message = ""
        self.message_timer = 0.0
        self.spawn_food()

    def start_game(self):
        self.reset_game()
        self.state = "play"

    def turn(self, direction):
        if self.state != "play":
            return
        if direction != OPPOSITE[self.direction]:
            self.pending_direction = direction

    def press_a(self, event=None):
        if self.state in ("title", "gameover"):
            self.start_game()
            return
        if self.state == "play" and self.slow_ready:
            self.slow_timer = 3.0
            self.slow_ready = False
            self.slow_charge = 0
            self.message = "SLOW BLOOM"
            self.message_timer = 0.7

    def press_b(self, event=None):
        if self.state == "title":
            self.root.destroy()
        elif self.state == "gameover":
            self.state = "title"

    def spawn_food(self):
        choices = [
            (x, y)
            for y in range(ROWS)
            for x in range(COLS)
            if (x, y) not in self.snake
        ]
        self.food = random.choice(choices) if choices else None

    def move_interval(self):
        base = max(0.085, 0.24 - self.score * 0.004)
        if self.slow_timer > 0:
            base *= 1.8
        return base

    def update(self, dt):
        if self.state != "play":
            return

        self.slow_timer = max(0.0, self.slow_timer - dt)
        self.message_timer = max(0.0, self.message_timer - dt)
        self.move_timer += dt

        interval = self.move_interval()
        if self.move_timer < interval:
            return
        self.move_timer -= interval

        self.direction = self.pending_direction
        dx, dy = DIRS[self.direction]
        hx, hy = self.snake[0]
        new_head = ((hx + dx) % COLS, (hy + dy) % ROWS)

        eating = new_head == self.food
        body_to_check = self.snake if eating else self.snake[:-1]

        if new_head in body_to_check:
            self.end_game()
            return

        self.snake.insert(0, new_head)

        if eating:
            self.score += 1
            if not self.slow_ready:
                self.slow_charge += 1
                if self.slow_charge >= 5:
                    self.slow_ready = True
                    self.message = "A READY"
                    self.message_timer = 0.7
            self.spawn_food()
        else:
            self.snake.pop()

    def end_game(self):
        self.state = "gameover"
        if self.score > self.high_score:
            self.high_score = self.score
            self.save_high_score()

    # -------------------------
    # Drawing helpers
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
            int(x0 * s), int(y0 * s), int(x1 * s), int(y1 * s),
            fill=fill, width=max(1, self.scale)
        )

    def text(self, x, y, txt, anchor="nw", size=5):
        s = self.scale
        self.canvas.create_text(
            int(x * s), int(y * s), text=txt, fill="white",
            anchor=anchor,
            font=("TkFixedFont", max(4, size * s)),
        )

    def cell_rect(self, cx, cy, inset=1):
        x0 = cx * CELL + inset
        y0 = HUD_H + cy * CELL + inset
        x1 = (cx + 1) * CELL - 1 - inset
        y1 = HUD_H + (cy + 1) * CELL - 1 - inset
        self.px_rect(x0, y0, x1, y1)

    def draw_food(self):
        if self.food is None:
            return
        cx, cy = self.food
        px = cx * CELL + 4
        py = HUD_H + cy * CELL + 4
        self.line(px - 2, py, px + 2, py)
        self.line(px, py - 2, px, py + 2)
        self.px_rect(px - 1, py - 1, px - 1, py - 1)
        self.px_rect(px + 1, py + 1, px + 1, py + 1)

    def render_title(self):
        self.text(64, 7, "BLOOM", anchor="n", size=7)
        self.text(64, 19, "SNAKE", anchor="n", size=7)
        self.text(64, 38, "A: PLAY", anchor="n", size=5)
        self.text(64, 47, f"BEST {self.high_score:03d}", anchor="n", size=5)
        self.text(64, 56, "B: EXIT", anchor="n", size=4)

    def render_hud(self):
        self.text(1, 0, f"{self.score:03d}", size=5)
        status = "A*" if self.slow_ready else "A."
        self.text(109, 0, status, size=5)
        self.line(0, HUD_H - 1, W - 1, HUD_H - 1)

    def render_play(self):
        self.render_hud()
        self.draw_food()

        for i, (cx, cy) in enumerate(self.snake):
            self.cell_rect(cx, cy, inset=1 if i == 0 else 2)

        if self.message_timer > 0:
            s = self.scale
            self.canvas.create_rectangle(
                25*s, 26*s, 103*s, 37*s,
                fill="black", outline="black"
            )
            self.text(64, 27, self.message, anchor="n", size=5)

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

    def loop(self):
        now = time.perf_counter()
        dt = min(0.05, now - self.last_time)
        self.last_time = now
        self.update(dt)
        self.render()
        self.root.after(FPS_MS, self.loop)


def main():
    parser = argparse.ArgumentParser(
        description="HAPPY JARZ Bloom Snake — exact 128x64 OLED-layout test app"
    )
    parser.add_argument(
        "--scale", type=int, default=1,
        help="integer desktop magnification; logical resolution remains 128x64"
    )
    args = parser.parse_args()

    root = tk.Tk()
    BloomSnake(root, scale=args.scale)
    root.mainloop()


if __name__ == "__main__":
    main()
