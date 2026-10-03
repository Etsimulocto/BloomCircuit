import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))
try:
    import plug_watch
except ImportError:
    plug_watch = None


@unittest.skipIf(plug_watch is None, "pyserial is required")
class WatcherTests(unittest.TestCase):
    def identify(self, record):
        class Port:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def write(self, data):
                self.command = data
                assert data == b"HELLO\n"
            def readline(self, limit): return record
        with patch.object(plug_watch.serial, "Serial", return_value=Port()):
            return plug_watch.identify("/dev/fake")

    def test_accepts_bloomscope(self):
        self.assertTrue(self.identify(b'{"type":"hello","device":"BloomScope","protocol":1}\n'))

    def test_rejects_other_firmware(self):
        self.assertFalse(self.identify(b'{"type":"hello","device":"HappyJarz","protocol":1}\n'))

    def test_rejects_incompatible_protocol(self):
        self.assertFalse(self.identify(b'{"type":"hello","device":"BloomScope","protocol":2}\n'))
