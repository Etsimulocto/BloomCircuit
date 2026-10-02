#!/usr/bin/env python3
"""Launch BloomSaver locally on Raspberry Pi without npm or external packages."""

from __future__ import annotations

import contextlib
import http.server
import os
import socket
import socketserver
import subprocess
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"


def free_port() -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind((HOST, 0))
        return int(sock.getsockname()[1])


def open_browser(url: str) -> None:
    commands = [
        ["chromium", "--app=" + url, "--start-maximized"],
        ["chromium-browser", "--app=" + url, "--start-maximized"],
        ["xdg-open", url],
    ]
    for command in commands:
        try:
            subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        except FileNotFoundError:
            continue
    print(f"Open this address in your browser: {url}")


def main() -> None:
    os.chdir(ROOT)
    port = free_port()
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer((HOST, port), handler) as server:
        url = f"http://{HOST}:{port}/"
        print(f"BloomSaver running at {url}")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.25)
        open_browser(url)
        try:
            while thread.is_alive():
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            server.shutdown()


if __name__ == "__main__":
    main()
