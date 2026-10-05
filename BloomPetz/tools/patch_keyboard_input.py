#!/usr/bin/env python3
"""Patch BloomPetz firmware so the mini desktop app can inject A/B/D-pad presses.

Adds a tiny serial command layer:
    KEY UP
    KEY DOWN
    KEY LEFT
    KEY RIGHT
    KEY A
    KEY B

The injected key is consumed by the same handleInput() state machine used by the
physical capacitive controls, so there is still only one pet/UI behavior layer.
"""

from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_keyboard_input.py <bloompetz_v0_1.ino>")

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

serial_marker = 'static String serialBuffer;\n'
serial_insert = '''static String serialBuffer;\nstatic Input usbPendingInput = NONE;\n'''
if 'static Input usbPendingInput = NONE;' not in s:
    if serial_marker not in s:
        raise SystemExit("keyboard patch failed: serialBuffer marker not found")
    s = s.replace(serial_marker, serial_insert, 1)

unknown_marker = '  Serial.printf("BP|ERROR|unknown_command=%s\\n",cmd.c_str());\n'
key_handler = '''  if (cmd.startsWith("KEY ")) {\n    String key=cmd.substring(4); key.trim(); key.toUpperCase();\n    if(key=="UP") usbPendingInput=UP;\n    else if(key=="DOWN") usbPendingInput=DOWN;\n    else if(key=="LEFT") usbPendingInput=LEFT;\n    else if(key=="RIGHT") usbPendingInput=RIGHT;\n    else if(key=="A") usbPendingInput=AKEY;\n    else if(key=="B") usbPendingInput=BKEY;\n    else { Serial.printf("BP|ERROR|bad_key=%s\\n",key.c_str()); return; }\n    Serial.printf("BP|KEY|name=%s\\n",key.c_str());\n    return;\n  }\n'''
if 'BP|KEY|name=' not in s:
    if unknown_marker not in s:
        raise SystemExit("keyboard patch failed: unknown-command marker not found")
    s = s.replace(unknown_marker, key_handler + unknown_marker, 1)

loop_marker = '''  serviceSerial();\n  Input in = pollInput();\n  if(in != NONE) handleInput(in);\n'''
loop_repl = '''  serviceSerial();\n  Input in = NONE;\n  if (usbPendingInput != NONE) {\n    in = usbPendingInput;\n    usbPendingInput = NONE;\n  } else {\n    in = pollInput();\n  }\n  if(in != NONE) handleInput(in);\n'''
if loop_repl not in s:
    if loop_marker not in s:
        raise SystemExit("keyboard patch failed: loop input marker not found")
    s = s.replace(loop_marker, loop_repl, 1)

p.write_text(s, encoding="utf-8")
print("BloomPetz USB keyboard input patch applied.")
