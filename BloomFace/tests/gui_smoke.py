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
app.face.mood=0;app.draw(3.0);root.update()
try:
    from PIL import ImageGrab
    ImageGrab.grab().save('/tmp/bloomface-preview.png')
except ImportError:pass
app.close()
print('All expressions, controls, drawing and clipboard: PASS')
