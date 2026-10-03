import sys
from pathlib import Path
import tkinter as tk
sys.path.insert(0,str(Path(__file__).parents[1]))
from bloomface import App,MOODS

root=tk.Tk();app=App(root,demo=True);root.update()
for i,name in enumerate(MOODS):
    app.face.mood=i;app.draw(3.0);root.update()
    assert len(app.canvas.find_all())>40,name
app.turn(1);app.tap();app.weird();app.draw(3.1);root.update()
app.copy_log();assert "WEIRD BURST" in root.clipboard_get()
# Verify speaker labels, text editing, panel toggles and session boundaries.
from console import SPEAKERS
from types import SimpleNamespace
for speaker in SPEAKERS:
    app.console.speaker.set(speaker)
    assert app.console.show_output(speaker,"Hello "+speaker,source="manual test")
assert all(speaker+" [manual test]" in app.console.speech.get("1.0","end") for speaker in SPEAKERS)
app.console.copy_speech();assert "GRIT [manual test]" in root.clipboard_get()
before=app.face.control
app.keyboard(SimpleNamespace(widget=app.console.draft),app.tap)
assert app.face.control==before,"Typing must not trigger face controls"
app.console.developer.set(False);app.console.toggle_dev();root.update()
app.console.camera_visible.set(True);app.console.toggle_camera();root.update()
assert app.console.developer.get() and app.console.camera.winfo_ismapped()
app.console.toggle_session()
before=(app.face.mood,app.face.control,app.face.surprise)
app.turn(1);app.tap();app.weird()
assert before==(app.face.mood,app.face.control,app.face.surprise)
assert app.usb.port is None
assert not app.console.show_output("BRO","Must not publish after session end")
app.console.toggle_session();app.face.control=0;app.turn(1)
assert app.face.mood!=before[0]
assert app.face.detent==2
app.console.camera_visible.set(False);app.console.toggle_camera()
app.console.speaker.set("BRO")
app.face.mood=0;app.draw(3.0);root.update()
try:
    from PIL import ImageGrab
    ImageGrab.grab().save('/tmp/bloomface-preview.png')
except ImportError:pass
app.close()
print('All expressions, controls, drawing and clipboard: PASS')
