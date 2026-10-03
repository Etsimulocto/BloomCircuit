"""Local webcam preview; capture lives in a stoppable child process."""
import glob
import multiprocessing as mp
import os
import queue
import tkinter as tk
from tkinter import ttk


def candidates():
    if os.name=='posix':
        return sorted(glob.glob('/dev/video*'),key=lambda p:int(p.removeprefix('/dev/video')) if p.removeprefix('/dev/video').isdigit() else 999)
    return list(range(4))


def capture_worker(messages,stop,source):
    cap=None
    def send(kind,value):
        try:messages.put_nowait((kind,value))
        except queue.Full:pass
    try:
        import cv2
        sources=candidates() if source=='Auto' else [int(source) if source.isdigit() else source]
        for device in sources:
            if stop.is_set():return
            cap=cv2.VideoCapture(device,cv2.CAP_V4L2 if os.name=='posix' else cv2.CAP_ANY)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH,640);cap.set(cv2.CAP_PROP_FRAME_HEIGHT,480)
                ok,frame=cap.read()
                if ok:break
            cap.release();cap=None
        else:
            send('error','No readable webcam. Check USB, permissions, or another camera app.');return
        send('status','Live camera: '+str(device))
        while not stop.is_set():
            rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
            h,w=rgb.shape[:2];scale=min(320/w,180/h)
            rgb=cv2.resize(rgb,(max(1,int(w*scale)),max(1,int(h*scale))))
            h,w=rgb.shape[:2]
            send('frame',f'P6\n{w} {h}\n255\n'.encode()+rgb.tobytes())
            if stop.wait(0.08):break
            ok,frame=cap.read()
            if not ok:
                send('error','Camera disconnected or stopped sending frames. Rescan to retry.');break
    except ImportError:
        send('error','Install python3-opencv, then restart the app.')
    except Exception as exc:
        send('error','Camera error: '+str(exc))
    finally:
        if cap is not None:cap.release()


class CameraPanel:
    def __init__(self,parent,app):
        self.app=app;self.process=None;self.messages=None;self.stop_event=None;self.photo=None;self.started=0;self.received=False
        self.frame=ttk.LabelFrame(parent,text='Camera preview · local',padding=6)
        self.source=tk.StringVar(value='Auto')
        self.selector=ttk.Combobox(self.frame,textvariable=self.source,state='readonly',width=14)
        self.selector.pack(fill='x');self.selector.bind('<<ComboboxSelected>>',lambda _:self.start())
        buttons=ttk.Frame(self.frame);buttons.pack(fill='x')
        ttk.Button(buttons,text='Detect / rescan',command=self.start).pack(side='left')
        ttk.Button(buttons,text='Stop',command=self.stop).pack(side='right')
        self.status=tk.StringVar(value='Preview stopped')
        ttk.Label(self.frame,textvariable=self.status,wraplength=290).pack(fill='x')
        self.image=ttk.Label(self.frame,anchor='center');self.image.pack(fill='x')

    def start(self):
        if not self.app.console.active:return
        self.stop(log=False)
        import time
        self.started=time.monotonic();self.received=False
        self.selector['values']=['Auto']+[str(x) for x in candidates()]
        self.status.set('Detecting camera…')
        context=mp.get_context('spawn')
        self.messages=context.Queue(maxsize=3);self.stop_event=context.Event()
        self.process=context.Process(target=capture_worker,args=(self.messages,self.stop_event,self.source.get()),daemon=True)
        self.process.start();self.app.log('Camera detection started: '+self.source.get())

    def poll(self):
        if not self.process:return
        import time
        for _ in range(4):
            try:kind,value=self.messages.get_nowait()
            except queue.Empty:break
            self.received=True
            if kind=='frame':
                self.photo=tk.PhotoImage(data=value,format='PPM');self.image.configure(image=self.photo)
            else:
                self.status.set(value);self.app.log(value)
                if kind=='error':self.stop(log=False,clear=False);return
        if time.monotonic()-self.started>12 and not self.received:
            self.stop(log=False);self.status.set('Camera detection timed out. Select a device and rescan.');self.app.log(self.status.get())
        elif not self.process.is_alive() and self.received:
            self.stop(log=False,clear=False)

    def stop(self,log=True,clear=True):
        if self.process:
            self.stop_event.set();self.process.join(timeout=0.15)
            if self.process.is_alive():self.process.terminate();self.process.join(timeout=0.2)
            self.messages.close();self.process=None
            if log:self.app.log('Camera stopped')
        if clear:
            self.image.configure(image='');self.photo=None;self.status.set('Preview stopped')
