"""Run under Xvfb: exercises real Tk drawing and CSV export in demo mode."""
import importlib.util
from pathlib import Path
import tempfile
import tkinter as tk
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("bloomscope", Path(__file__).parents[1] / "bloomscope.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
root = tk.Tk()
app = m.App(root, demo=True)
root.update()
for mode in m.MODES:
    app.select(mode)
    app.start()
    app.tick()
    root.update()
    assert app.readout.get()
    if mode in ("SCOPE", "LOGIC"):
        assert app.capture and app.canvas.find_all()
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory) / "capture.csv"
            with patch.object(m.filedialog, "asksaveasfilename", return_value=str(dest)):
                app.save()
            rows = dest.read_text().splitlines()
            assert len(rows) == 129 and rows[1].startswith("True," + mode)
with patch.object(m.messagebox, "askokcancel", return_value=True):
    app.arm()
app.tick()
assert app.mode == "CONT"
app.pause()
assert not app.running
app.close()
print("Tk modes, plots, CSV exports, continuity arm/stop: PASS")
