#!/usr/bin/env python3
"""
============================================================
BLOOMCORE MODULE
============================================================
identity:
  name: HAPPY JARZ — Jar Pong
  module: jar_pong
  version: 0.1
  format: bloomcore/v1.3

purpose:
  Standalone 128x64 landscape monochrome OLED minigame.
  Single-player pong tuned for discrete capacitive-touch controls.

display:
  logical resolution: 128x64 pixels
  orientation: landscape
  colors: monochrome
  optional desktop scale: --scale N

controls:
  LEFT / RIGHT = move paddle one fixed slot per tap
  A / Z / Enter = serve / restart
  B / X / Escape = back / exit
  R = reset best rally on title screen

gameplay:
  Keep the ball alive by bouncing it off the bottom paddle.
  Paddle moves across 10 fixed touch-friendly slots.
  Rally score increases every successful paddle hit.
  Ball speed ramps up as the rally grows.
  Missing the ball ends the run.
  Best rally persists beside this script.

DO NOT:
  Change the 128x64 logical coordinate system when porting to OLED.
  Couple this test module to the main HAPPY JARZ firmware yet.
============================================================
"""

import argparse
import math
import random
import time
import tkinter as tk
from pathlib import Path

W = 128
H = 64
HUD_H = 9
FPS_MS = 16
SAVE_PATH = Path(__file__).with_name("jar_pong_best.txt")

SLOT_COUNT = 10
SLOT_LEFT = 9
SLOT_RIGHT = W - 10
SLOT_X = [
    SLOT_LEFT + i * (SLOT_RIGHT - SLOT_LEFT) / (SLOT_COUNT - 1)
    for i in range(SLOT_COUNT)
]

PADDLE_Y = 58
PADDLE_W = 18
BALL_R = 2


class JarPong:
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
        root.title("Jar Pong — 128x64 OLED Test")
        root.resizable(False, False)

        self.state = "title"
        self.best = self.load_best()
        self.last_time = time.perf_counter()
        self.bind_keys()
        self.reset_round()
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

    def step_left(self, event=None):
        if self.state in ("ready", "play"):
            self.paddle_slot = max(0, self.paddle_slot - 1)
            self.paddle_x = SLOT_X[self.paddle_slot]
            if self.state == "ready":
                self.ball_x = self.paddle_x

    def step_right(self, event=None):
        if self.state in ("ready", "play"):
            self.paddle_slot = min(SLOT_COUNT - 1, self.paddle_slot + 1)
            self.paddle_x = SLOT_X[self.paddle_slot]
            if self.state == "ready":
                self.ball_x = self.paddle_x

    def press_a(self, event=None):
        if self.state == "title":
            self.start_game()
        elif self.state == "ready":
            self.serve()
        elif self.state == "gameover":
            self.start_game()

    def press_b(self, event=None):
        if self.state == "title":
            self.root.destroy()
        elif self.state in ("ready", "play", "gameover"):
            self.state = "title"

    def reset_round(self):
        self.rally = 0
        self.paddle_slot = (SLOT_COUNT - 1) // 2
        self.paddle_x = SLOT_X[self.paddle_slot]
        self.ball_x = self.paddle_x
        self.ball_y = PADDLE_Y - 4
        self.ball_vx = 0.0
        self.ball_vy = 0.0
        self.flash_timer = 0.0
        self.message = ""
        self.message_timer = 0.0

    def start_game(self):
        self.reset_round()
        self.state = "ready"

    def serve(self):
        if self.state != "ready":
            return
        angle = random.uniform(-0.75, 0.75)
        speed = 28.0
        self.ball_vx = math.sin(angle) * speed
        self.ball_vy = -abs(math.cos(angle) * speed)
        self.state = "play"
        self.message = ""

    def current_speed(self):
        return min(54.0, 28.0 + self.rally * 1.8)

    def normalize_speed(self):
        mag = math.hypot(self.ball_vx, self.ball_vy)
        if mag <= 0:
            return
        target = self.current_speed()
        self.ball_vx = self.ball_vx / mag * target
        self.ball_vy = self.ball_vy / mag * target

    def paddle_hit(self):
        self.rally += 1
        if self.rally > self.best:
            self.best = self.rally
            self.save_best()

        offset = (self.ball_x - self.paddle_x) / (PADDLE_W / 2)
        offset = max(-1.0, min(1.0, offset))
        speed = self.current_speed()

        self.ball_vx = offset * speed * 0.75
        vertical = max(12.0, math.sqrt(max(1.0, speed * speed - self.ball_vx * self.ball_vx)))
        self.ball_vy = -vertical
        self.normalize_speed()

        self.flash_timer = 0.08
        if self.rally in (5, 10, 20, 30):
            self.message = "FASTER!"
            self.message_timer = 0.55

    def end_game(self):
        self.state = "gameover"
        self.message = "MISS!"
        self.message_timer = 0.8

    def update(self, dt):
        self.flash_timer = max(0.0, self.flash_timer - dt)
        self.message_timer = max(0.0, self.message_timer - dt)

        if self.state != "play":
            return

        self.ball_x += self.ball_vx * dt
        self.ball_y += self.ball_vy * dt

        if self.ball_x - BALL_R <= 1:
            self.ball_x = 1 + BALL_R
            self.ball_vx = abs(self.ball_vx)
        elif self.ball_x + BALL_R >= W - 2:
            self.ball_x = W - 2 - BALL_R
            self.ball_vx = -abs(self.ball_vx)

        if self.ball_y - BALL_R <= HUD_H + 1:
            self.ball_y = HUD_H + 1 + BALL_R
            self.ball_vy = abs(self.ball_vy)

        paddle_left = self.paddle_x - PADDLE_W / 2
        paddle_right = self.paddle_x + PADDLE_W / 2
        ball_bottom = self.ball_y + BALL_R

        if (
            self.ball_vy > 0
            and ball_bottom >= PADDLE_Y
            and self.ball_y <= PADDLE_Y + 3
            and self.ball_x + BALL_R >= paddle_left
            and self.ball_x - BALL_R <= paddle_right
        ):
            self.ball_y = PADDLE_Y - BALL_R - 1
            self.paddle_hit()

        if self.ball_y - BALL_R > H:
            self.end_game()

    def px_rect(self, x0, y0, x1, y1, fill="white"):
        s = self.scale
        self.canvas.create_rectangle(
            int(x0*s), int(y0*s),
            int((x1+1)*s-1), int((y1+1)*s-1),
            fill=fill, outline=fill,
        )

    def line(self, x0, y0, x1, y1, fill="white"):
        s = self.scale
        self.canvas.create_line(
            int(x0*s), int(y0*s), int(x1*s), int(y1*s),
            fill=fill, width=max(1, self.scale)
        )

    def text(self, x, y, txt, anchor="nw", size=5):
        s = self.scale
        self.canvas.create_text(
            int(x*s), int(y*s), text=txt, fill="white", anchor=anchor,
            font=("TkFixedFont", max(4, size*s)),
        )

    def draw_ball(self):
        x = int(round(self.ball_x))
        y = int(round(self.ball_y))
        self.px_rect(x-1, y-1, x+1, y+1)
        self.px_rect(x, y-2, x, y+2)
        self.px_rect(x-2, y, x+2, y)

    def draw_paddle(self):
        cx = int(round(self.paddle_x))
        half = PADDLE_W // 2
        self.px_rect(cx-half, PADDLE_Y, cx+half, PADDLE_Y+2)
        self.px_rect(cx-half+2, PADDLE_Y-1, cx+half-2, PADDLE_Y-1)

    def render_title(self):
        self.text(64, 8, "JAR PONG", anchor="n", size=7)
        self.text(64, 27, "A: PLAY", anchor="n", size=5)
        self.text(64, 39, f"BEST {self.best:02d}", anchor="n", size=5)
        self.text(64, 53, "B: EXIT", anchor="n", size=4)

    def render_game(self):
        self.text(1, 0, f"RALLY {self.rally:02d}", size=5)
        self.text(127, 0, f"BEST {self.best:02d}", anchor="ne", size=5)
        self.line(0, 8, 127, 8)

        for sx in SLOT_X:
            self.px_rect(int(round(sx)), 63, int(round(sx)), 63)

        self.draw_paddle()
        self.draw_ball()

        if self.state == "ready":
            self.text(64, 23, "A: SERVE", anchor="n", size=5)

        if self.message_timer > 0 and self.message:
            self.px_rect(43, 26, 85, 40, fill="black")
            self.text(64, 29, self.message, anchor="n", size=5)

        if self.flash_timer > 0:
            self.px_rect(0, 9, 1, 63)
            self.px_rect(126, 9, 127, 63)

    def render_gameover(self):
        self.text(64, 10, "BALL LOST", anchor="n", size=6)
        self.text(64, 28, f"RALLY {self.rally:02d}", anchor="n", size=5)
        self.text(64, 39, f"BEST  {self.best:02d}", anchor="n", size=5)
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
        dt = min(0.04, now - self.last_time)
        self.last_time = now
        self.update(dt)
        self.render()
        self.root.after(FPS_MS, self.loop)


def main():
    parser = argparse.ArgumentParser(description="HAPPY JARZ Jar Pong — 128x64 OLED test app")
    parser.add_argument("--scale", type=int, default=1)
    args = parser.parse_args()

    root = tk.Tk()
    JarPong(root, scale=args.scale)
    root.mainloop()


if __name__ == "__main__":
    main()
