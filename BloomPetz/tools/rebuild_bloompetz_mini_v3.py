#!/usr/bin/env python3
"""Rebuild BloomPetz Mini as one clean System/Petz/DND-aware desktop app.

This intentionally replaces ONLY desktop/bloompetz_mini.py. Firmware is untouched.
It consolidates the accumulated local Mini patches into one authoritative app:
- 21-column mirror support
- DND detection from BP|SCREEN content
- DND hides pet name + side art completely
- BLOOM SYSTEM / BloomPetz restore normal chrome
- six clickable controls: arrows + A/B
- keyboard: arrows + A/B only
- USB host-time sync on connect and every 60 seconds
- serial ownership behavior retained
"""
from pathlib import Path
import sys

APP = r'''#!/usr/bin/env python3
from __future__ import annotations

import glob
import json
import os
import queue
import random
import subprocess
import threading
import time
import tkinter as tk

try:
    import serial
except ImportError as exc:
    raise SystemExit("pyserial is required: sudo apt install -y python3-serial") from exc

BAUD = 115200
POLL_SECONDS = 0.20
STABLE_SECONDS = 2.0
DISCONNECT_GRACE_SEC = 3.0
CONFIG_PATH = os.path.expanduser("~/.config/bloompetz/mini.json")
ASSIGNED_PORT = os.environ.get("BLOOMPETZ_PORT", "").strip()

SCREEN_W = 192
SCREEN_H = 96
HEADER_H = 18
CONTROL_H = 64
SIDE_W = 18
SIDE_PARTICLES = 8
SIDE_TICK_MS = 120
MIRROR_COLS = 21
FONT = ("DejaVu Sans Mono", 10, "bold")
HEADER_FONT = ("DejaVu Sans", 7, "bold")
BUTTON_FONT = ("DejaVu Sans", 11, "bold")

COLORS = [
    "#000000", "#ffffff", "#ff2d2d", "#ff7a00", "#ffd400", "#80ff00",
    "#00d45a", "#00c7a8", "#00e5ff", "#39a0ff", "#3155ff", "#7b3cff",
    "#d43cff", "#ff3cab", "#9b9b9b", "#8a4f20",
]


def programmer_running() -> bool:
    try:
        p = subprocess.run(["pgrep", "-f", "arduino-cli|esptool"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           check=False)
        return p.returncode == 0
    except Exception:
        return False


def serial_ports() -> list[str]:
    return sorted(glob.glob("/dev/ttyACM*"))


def _rgb(c: str):
    h = c.lstrip("#")
    return int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)


def _brightness(c: str) -> float:
    r,g,b = _rgb(c)
    return 0.299*r + 0.587*g + 0.114*b


THEMES = [(fg,bg) for fg in COLORS for bg in COLORS
          if fg != bg and abs(_brightness(fg)-_brightness(bg)) >= 80]


class BloomPetzMini(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("BloomPetz Mini")
        self.geometry(f"{SCREEN_W}x{SCREEN_H + HEADER_H + CONTROL_H}")
        self.resizable(False, False)
        self.overrideredirect(True)

        self.rx: queue.Queue[tuple] = queue.Queue()
        self.running = True
        self.ser: serial.Serial | None = None
        self.ser_lock = threading.Lock()
        self.connected_port: str | None = None
        self.key_down: set[str] = set()
        self.screen_lines = [" " * MIRROR_COLS for _ in range(4)]
        self.pet_name = "NO PET"
        self.dnd_mode = False
        self.last_host_time_send = 0.0
        self.text_color, self.bg_color = self._load_theme()
        self._drag_x = self._drag_y = 0
        self.side_left = [self._new_particle(True) for _ in range(SIDE_PARTICLES)]
        self.side_right = [self._new_particle(True) for _ in range(SIDE_PARTICLES)]

        self.configure(bg="#151515")
        self._build_ui()
        self._bind_keys()
        self.protocol("WM_DELETE_WINDOW", self.close_app)
        threading.Thread(target=self._serial_worker, daemon=True).start()
        self.after(25, self._drain_rx)
        self.after(100, self.focus_force)
        self.after(SIDE_TICK_MS, self._animate_side_art)

    def _new_particle(self, start_anywhere=False):
        return {"x": random.randint(2,SIDE_W-3),
                "y": random.randint(0,SCREEN_H) if start_anywhere else random.randint(-24,-2),
                "speed": random.randint(1,4), "shape": random.randint(0,4)}

    def _build_ui(self):
        self.header = tk.Frame(self, bg="#151515", height=HEADER_H)
        self.header.pack(fill="x")
        self.header.pack_propagate(False)
        self.header.bind("<ButtonPress-1>", self._drag_start)
        self.header.bind("<B1-Motion>", self._drag_move)

        self.title_label = tk.Label(self.header, text=self.pet_name, bg="#151515",
                                    fg="#d8d8d8", font=HEADER_FONT, anchor="w")
        self.title_label.pack(side="left", padx=(4,1))
        self.title_label.bind("<ButtonPress-1>", self._drag_start)
        self.title_label.bind("<B1-Motion>", self._drag_move)

        close = tk.Label(self.header, text="×", bg="#151515", fg="#dddddd",
                         width=2, font=("DejaVu Sans",9,"bold"), cursor="hand2")
        close.pack(side="right")
        close.bind("<Button-1>", lambda _e: self.close_app())

        self.next_color = tk.Label(self.header, text="▶", bg="#151515", fg="#eeeeee",
                                   width=3, font=("DejaVu Sans",8,"bold"), cursor="hand2")
        self.next_color.pack(side="right")
        self.next_color.bind("<Button-1>", self._theme_click)
        self.color_label = tk.Label(self.header, text="COLOR", bg="#151515", fg=self.text_color,
                                    width=5, font=("DejaVu Sans",7,"bold"), cursor="hand2")
        self.color_label.pack(side="right")
        self.color_label.bind("<Button-1>", self._theme_click)
        self.prev_color = tk.Label(self.header, text="◀", bg="#151515", fg="#eeeeee",
                                   width=3, font=("DejaVu Sans",8,"bold"), cursor="hand2")
        self.prev_color.pack(side="right")
        self.prev_color.bind("<Button-1>", self._theme_click)

        self.screen = tk.Frame(self, bg=self.bg_color, width=SCREEN_W, height=SCREEN_H)
        self.screen.pack(fill="x")
        self.screen.pack_propagate(False)

        self.left_art = tk.Canvas(self.screen, width=SIDE_W, height=SCREEN_H,
                                  bg=self.bg_color, highlightthickness=0, bd=0)
        self.right_art = tk.Canvas(self.screen, width=SIDE_W, height=SCREEN_H,
                                   bg=self.bg_color, highlightthickness=0, bd=0)
        self.left_art.place(x=0,y=0)
        self.right_art.place(x=SCREEN_W-SIDE_W,y=0)

        self.line_labels = []
        for i in range(4):
            label = tk.Label(self.screen, text=self.screen_lines[i], bg=self.bg_color,
                             fg=self.text_color, font=FONT, anchor="center", justify="center",
                             padx=0, pady=0)
            label.place(relx=0.5, rely=(i+0.5)/4.0, anchor="center")
            self.line_labels.append(label)

        self.controls = tk.Frame(self, bg="#151515", height=CONTROL_H)
        self.controls.pack(fill="x")
        self.controls.pack_propagate(False)

        def add_btn(text,key,x,y,w=38,h=28):
            b = tk.Button(self.controls, text=text,
                          command=lambda k=key:self._button_key(k),
                          font=BUTTON_FONT, bd=1, relief="raised",
                          takefocus=False, cursor="hand2")
            b.place(x=x,y=y,width=w,height=h)
            return b

        # Matches physical six-input controller exactly.
        self.btn_up = add_btn("↑","UP",40,1)
        self.btn_left = add_btn("←","LEFT",1,31)
        self.btn_down = add_btn("↓","DOWN",40,31)
        self.btn_right = add_btn("→","RIGHT",79,31)
        self.btn_a = add_btn("A","A",128,5,28,28)
        self.btn_b = add_btn("B","B",161,30,28,28)
        self._draw_side_art()

    def _draw_particle(self, canvas, p):
        x,y,c,shape = p["x"],p["y"],self.text_color,p["shape"]
        if shape == 0: canvas.create_rectangle(x,y,x+1,y+1,fill=c,outline=c)
        elif shape == 1:
            canvas.create_line(x-2,y,x+2,y,fill=c); canvas.create_line(x,y-2,x,y+2,fill=c)
        elif shape == 2: canvas.create_oval(x-1,y-1,x+2,y+2,outline=c)
        elif shape == 3: canvas.create_line(x-2,y-2,x+2,y+2,fill=c)
        else: canvas.create_rectangle(x-1,y-1,x+1,y+1,fill=c,outline=c)

    def _draw_side_art(self):
        if self.dnd_mode:
            return
        for canvas in (self.left_art,self.right_art):
            canvas.delete("all"); canvas.configure(bg=self.bg_color)
        for p in self.side_left: self._draw_particle(self.left_art,p)
        for p in self.side_right: self._draw_particle(self.right_art,p)

    def _animate_side_art(self):
        if not self.running: return
        if not self.dnd_mode:
            for particles in (self.side_left,self.side_right):
                for i,p in enumerate(particles):
                    p["y"] += p["speed"]
                    if p["y"] > SCREEN_H+4: particles[i] = self._new_particle(False)
            self._draw_side_art()
        self.after(SIDE_TICK_MS,self._animate_side_art)

    def _bind_keys(self):
        mapping = {"Up":"UP","Down":"DOWN","Left":"LEFT","Right":"RIGHT",
                   "a":"A","A":"A","b":"B","B":"B"}
        for keysym,bpkey in mapping.items():
            self.bind_all(f"<KeyPress-{keysym}>", lambda _e,k=bpkey:self._key_press(k))
            self.bind_all(f"<KeyRelease-{keysym}>", lambda _e,k=bpkey:self._key_release(k))

    def _key_press(self,key):
        if key in self.key_down: return "break"
        self.key_down.add(key); self.send(f"KEY {key}"); return "break"

    def _key_release(self,key):
        self.key_down.discard(key); return "break"

    def _button_key(self,key):
        self.send(f"KEY {key}")
        return "break"

    def _set_dnd_mode(self, enabled: bool):
        enabled = bool(enabled)
        if enabled == self.dnd_mode: return
        self.dnd_mode = enabled
        if enabled:
            self.left_art.place_forget(); self.right_art.place_forget()
            self.title_label.configure(text="")
        else:
            self.left_art.place(x=0,y=0); self.right_art.place(x=SCREEN_W-SIDE_W,y=0)
            self.title_label.configure(text=self.pet_name)
            self._draw_side_art()

    def _looks_like_dnd(self, rows):
        joined = " ".join(r.strip() for r in rows)
        # DND has 12-column dungeon geometry and/or its own game/menu vocabulary.
        if any(len(r.rstrip()) > 16 for r in rows): return True
        tokens = ("EXPLORE","ATTACK","HEALTH ","ARMOR CLASS","IRON SWORD",
                  "CHARACTER","INVENTORY","SYMBOLS","AIM","DAMAGE ","ROLL ",
                  "GOLD ","LEVEL ","EXPERIENCE ","KEYS ")
        if any(t in joined for t in tokens): return True
        # Room rows visibly contain the 12-cell wall/map grammar.
        if any(r.count("#") >= 4 for r in rows): return True
        # BLOOM SYSTEM and BloomPetz frames force DND mode off.
        if "BLOOM SYSTEM" in joined or "BLOOMPETZ" in joined: return False
        return self.dnd_mode

    def _drag_start(self,event):
        self._drag_x=event.x_root-self.winfo_x(); self._drag_y=event.y_root-self.winfo_y()

    def _drag_move(self,event):
        self.geometry(f"+{event.x_root-self._drag_x}+{event.y_root-self._drag_y}")

    def _theme_click(self,_event=None):
        old=(self.text_color,self.bg_color)
        choices=[t for t in THEMES if t != old]
        self.text_color,self.bg_color=random.choice(choices or THEMES)
        self._apply_theme(); self._save_theme(); return "break"

    def _apply_theme(self):
        self.screen.configure(bg=self.bg_color); self.color_label.configure(fg=self.text_color)
        for label in self.line_labels: label.configure(fg=self.text_color,bg=self.bg_color)
        self._draw_side_art()

    def _load_theme(self):
        try:
            with open(CONFIG_PATH,"r",encoding="utf-8") as f: d=json.load(f)
            pair=(d.get("text_color"),d.get("bg_color"))
            if pair in THEMES: return pair
        except Exception: pass
        return "#00e5ff","#000000"

    def _save_theme(self):
        try:
            os.makedirs(os.path.dirname(CONFIG_PATH),exist_ok=True)
            with open(CONFIG_PATH,"w",encoding="utf-8") as f:
                json.dump({"text_color":self.text_color,"bg_color":self.bg_color},f)
        except Exception: pass

    def _set_connected(self,connected):
        self.title_label.configure(fg="#d8d8d8" if connected else "#777777")

    def _choose_port(self):
        if ASSIGNED_PORT: return ASSIGNED_PORT if os.path.exists(ASSIGNED_PORT) else None
        ports=serial_ports(); return ports[0] if ports else None

    def _open_port(self,port):
        s=serial.Serial(); s.port=port; s.baudrate=BAUD; s.timeout=.25; s.write_timeout=.25
        s.dtr=False; s.rts=False; s.open(); s.dtr=False; s.rts=False; return s

    def _send_host_time(self):
        now=time.time(); lt=time.localtime(now)
        off=-time.altzone if lt.tm_isdst>0 and time.daylight else -time.timezone
        self.send(f"SET HOSTTIME {int(now)} {int(off//60)}")
        self.last_host_time_send=time.monotonic()

    def _serial_worker(self):
        seen_since=None
        while self.running:
            if programmer_running(): time.sleep(POLL_SECONDS); continue
            if self.ser is None:
                port=self._choose_port()
                if port is None:
                    if ASSIGNED_PORT: self.rx.put(("quit",)); return
                    seen_since=None; time.sleep(POLL_SECONDS); continue
                if seen_since is None: seen_since=time.monotonic()
                if time.monotonic()-seen_since<STABLE_SECONDS: time.sleep(POLL_SECONDS); continue
                try: s=self._open_port(port)
                except Exception: time.sleep(.4); continue
                with self.ser_lock: self.ser=s; self.connected_port=port
                self.rx.put(("status",True)); time.sleep(.15)
                self.send("HELLO"); self.send("GET SCREEN"); self.send("GET STATUS"); self._send_host_time()
                continue
            if time.monotonic()-self.last_host_time_send>=60.0: self._send_host_time()
            port=self.connected_port
            if not port: self.rx.put(("quit",)); return
            if not os.path.exists(port):
                missing=time.monotonic()
                while self.running and not os.path.exists(port):
                    if time.monotonic()-missing>=DISCONNECT_GRACE_SEC: self.rx.put(("quit",)); return
                    time.sleep(POLL_SECONDS)
                continue
            try: raw=self.ser.readline() if self.ser else b""
            except Exception:
                time.sleep(POLL_SECONDS); continue
            if raw:
                line=raw.decode("utf-8",errors="replace").rstrip("\r\n")
                if line: self.rx.put(("line",line))

    def send(self,command):
        with self.ser_lock: s=self.ser
        if s is None or not s.is_open: return
        try: s.write((command.strip()+"\n").encode("utf-8")); s.flush()
        except Exception: pass

    @staticmethod
    def _fields(line):
        out={}
        for part in line.split("|")[2:]:
            if "=" in part:
                k,v=part.split("=",1); out[k]=v
        return out

    def _drain_rx(self):
        try:
            while True:
                item=self.rx.get_nowait()
                if item[0]=="status": self._set_connected(bool(item[1]))
                elif item[0]=="line": self._handle_line(item[1])
                elif item[0]=="quit": self.close_app(); return
        except queue.Empty: pass
        if self.running: self.after(25,self._drain_rx)

    def _handle_line(self,line):
        if line.startswith("BP|STATUS|"):
            f=self._fields(line); occupied=f.get("occupied","0")=="1"; name=f.get("name","").strip()
            self.pet_name=name[:12] if occupied and name else "NO PET"
            if not self.dnd_mode: self.title_label.configure(text=self.pet_name)
            return
        if line.startswith("BP|BOOT|") or line.startswith("BP|IDENTITY|"):
            self._set_connected(True); self.send("GET STATUS"); return
        if not line.startswith("BP|SCREEN|"): return
        fields=self._fields(line)
        raw=[fields.get(str(i+1),self.screen_lines[i]).rstrip() for i in range(4)]
        self._set_dnd_mode(self._looks_like_dnd(raw))
        for i in range(4):
            text=raw[i][:MIRROR_COLS].ljust(MIRROR_COLS)
            self.screen_lines[i]=text; self.line_labels[i].configure(text=text)

    def close_app(self):
        if not self.running: return
        self.running=False
        with self.ser_lock: s=self.ser; self.ser=None
        try:
            if s: s.close()
        except Exception: pass
        self.destroy()


if __name__ == "__main__":
    BloomPetzMini().mainloop()
'''


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: rebuild_bloompetz_mini_v3.py <bloompetz_v0_1.ino>")
    fw = Path(sys.argv[1]).expanduser().resolve()
    if not fw.exists():
        raise SystemExit(f"firmware not found: {fw}")
    app = fw.parents[2] / "desktop" / "bloompetz_mini.py"
    if not app.exists():
        raise SystemExit(f"desktop app not found: {app}")
    backup = app.with_suffix(".py.pre_v3_backup")
    if not backup.exists():
        backup.write_text(app.read_text())
    app.write_text(APP)
    print(f"BloomPetz Mini V3 rebuilt: {app}")
    print(f"Backup preserved: {backup}")
    print("Firmware untouched. Restart Mini to use consolidated System/Petz/DND UI.")


if __name__ == "__main__":
    main()
