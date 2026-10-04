#!/usr/bin/env python3
import glob
import os
import subprocess
import time

try:
    import serial
except ImportError:
    serial = None

APP = os.path.expanduser('~/BloomCircuit/happyjarz-controller/tools/happyjarz_meter.py')
BAUD = 115200
STABLE_SECONDS = 2.0
POLL_SECONDS = 0.25
HANDSHAKE_TIMEOUT = 1.0


def programmer_running():
    """Do not grab serial devices while Arduino/esptool is compiling or flashing."""
    try:
        result = subprocess.run(
            ['pgrep', '-f', 'arduino-cli|esptool'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


def serial_ports():
    """Return current USB CDC/ACM serial ports in deterministic order."""
    return sorted(glob.glob('/dev/ttyACM*'))


def is_bloompulse(port):
    """Identify BloomPulse by its firmware protocol, not by USB port number."""
    if serial is None:
        return False

    s = None
    try:
        s = serial.Serial()
        s.port = port
        s.baudrate = BAUD
        s.timeout = 0.15
        s.write_timeout = 0.25
        s.dtr = False
        s.rts = False
        s.open()
        s.dtr = False
        s.rts = False

        # Do not enable streaming during discovery. GET has a small, unique reply.
        try:
            s.reset_input_buffer()
        except Exception:
            pass
        s.write(b'GET\n')
        s.flush()

        deadline = time.monotonic() + HANDSHAKE_TIMEOUT
        while time.monotonic() < deadline:
            raw = s.readline()
            if not raw:
                continue
            line = raw.decode(errors='replace').strip()
            if line.startswith('HJ|EQCFG|'):
                return True
        return False
    except Exception:
        return False
    finally:
        try:
            if s is not None:
                s.close()
        except Exception:
            pass


def launch_bloompulse(port):
    env = os.environ.copy()
    env['BLOOMPULSE_PORT'] = port
    try:
        return subprocess.Popen(['python3', APP], env=env)
    except Exception:
        return None


def main():
    # first_seen tracks USB stability. probed tracks devices already identified or
    # rejected during the current plug-in session. launched prevents a manually
    # closed app from immediately reopening while the same controller stays plugged in.
    first_seen = {}
    probed = set()
    launched = set()
    proc = None
    active_port = None

    while True:
        now = time.monotonic()
        ports = set(serial_ports())

        # Forget state only after a physical unplug. Replugging then rearms discovery.
        for port in list(first_seen):
            if port not in ports:
                first_seen.pop(port, None)
                probed.discard(port)
                launched.discard(port)
                if port == active_port:
                    active_port = None

        for port in ports:
            first_seen.setdefault(port, now)

        if proc is not None and proc.poll() is not None:
            proc = None
            active_port = None

        if proc is None and not programmer_running():
            for port in sorted(ports):
                if port in probed or port in launched:
                    continue
                if now - first_seen.get(port, now) < STABLE_SECONDS:
                    continue

                # Probe a newly stable device once. Non-BloomPulse ESP32s are then
                # ignored until they are physically unplugged/replugged.
                probed.add(port)
                if not is_bloompulse(port):
                    continue

                proc = launch_bloompulse(port)
                if proc is not None:
                    launched.add(port)
                    active_port = port
                break

        time.sleep(POLL_SECONDS)


if __name__ == '__main__':
    main()
