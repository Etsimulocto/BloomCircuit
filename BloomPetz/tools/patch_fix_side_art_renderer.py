#!/usr/bin/env python3
"""Ensure BloomPetz side art is drawn inside physicalOledRender(), not a boot/splash sendBuffer.

Safe repair for sketches already patched with BLOOMPETZ_SIDE_SCROLL_ART_V1.
"""
from pathlib import Path
import sys

MARKER = "// BLOOMPETZ_SIDE_ART_RENDERER_FIX_V1"


def find_function_span(src: str, signature: str):
    start = src.find(signature)
    if start < 0:
        return None
    brace = src.find('{', start)
    if brace < 0:
        return None
    depth = 0
    for i in range(brace, len(src)):
        c = src[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return start, i + 1
    return None


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_fix_side_art_renderer.py <bloompetz_v0_1.ino>")

    p = Path(sys.argv[1]).expanduser().resolve()
    s = p.read_text()

    if MARKER in s:
        print("Side-art renderer fix already applied.")
        return

    if "BLOOMPETZ_SIDE_SCROLL_ART_V1" not in s:
        raise SystemExit("Side-art patch marker not found. Apply side-art patch first.")

    span = find_function_span(s, "static void physicalOledRender")
    if not span:
        raise SystemExit("physicalOledRender() not found")

    # Remove existing drawSideArt() calls everywhere. We will add exactly one in the
    # real framebuffer renderer so every redraw preserves the decoration.
    s = s.replace("  drawSideArt();\n", "")

    span = find_function_span(s, "static void physicalOledRender")
    if not span:
        raise SystemExit("physicalOledRender() disappeared unexpectedly")
    a, b = span
    fn = s[a:b]

    send = fn.rfind("oled.sendBuffer();")
    if send < 0:
        raise SystemExit("oled.sendBuffer() not found inside physicalOledRender()")

    fn = fn[:send] + "drawSideArt();\n  " + fn[send:]
    s = s[:a] + fn + s[b:]

    # Place marker near side-art marker.
    s = s.replace("// BLOOMPETZ_SIDE_SCROLL_ART_V1\n",
                  "// BLOOMPETZ_SIDE_SCROLL_ART_V1\n// BLOOMPETZ_SIDE_ART_RENDERER_FIX_V1\n", 1)

    p.write_text(s)
    print(f"Fixed side-art renderer in {p}")
    print("drawSideArt() now runs inside physicalOledRender() before oled.sendBuffer().")


if __name__ == "__main__":
    main()
