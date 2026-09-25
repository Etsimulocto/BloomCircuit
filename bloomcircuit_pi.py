#!/usr/bin/env python3
"""BloomCircuit Raspberry Pi offline desktop launcher.

Runs the existing static BloomCircuit files on localhost and opens Chromium
in app mode. No internet connection is required.
"""
from __future__ import annotations

import contextlib
import http.server
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser

APP_DIR = Path(__file__).resolve().parent
HOST = "127.0.0.1"


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, 0))
        return int(sock.getsockname()[1])


def find_chromium() -> str | None:
    candidates = (
        "chromium-browser",
        "chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
    )
    for candidate in candidates:
        found = shutil.which(candidate)
        if found:
            return found
        if os.path.isabs(candidate) and os.path.exists(candidate):
            return candidate
    return None


def main() -> int:
    os.chdir(APP_DIR)
    port = free_port()
    url = f"http://{HOST}:{port}/"

    handler = lambda *args, **kwargs: QuietHandler(
        *args, directory=str(APP_DIR), **kwargs
    )
    server = http.server.ThreadingHTTPServer((HOST, port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    chromium = find_chromium()
    browser = None

    try:
        if chromium:
            profile_dir = Path.home() / ".local" / "share" / "bloomcircuit" / "chromium"
            profile_dir.mkdir(parents=True, exist_ok=True)
            browser = subprocess.Popen(
                [
                    chromium,
                    f"--app={url}",
                    "--start-maximized",
                    "--no-first-run",
                    "--disable-session-crashed-bubble",
                    "--disable-features=Translate",
                    f"--user-data-dir={profile_dir}",
                ]
            )
            return browser.wait()

        print("Chromium was not found. Opening BloomCircuit in the default browser.")
        print(f"BloomCircuit: {url}")
        webbrowser.open(url)
        print("Press Ctrl+C here when you are finished.")
        while True:
            time.sleep(3600)

    except KeyboardInterrupt:
        return 0
    finally:
        server.shutdown()
        server.server_close()
        if browser and browser.poll() is None:
            with contextlib.suppress(Exception):
                browser.terminate()


if __name__ == "__main__":
    sys.exit(main())
