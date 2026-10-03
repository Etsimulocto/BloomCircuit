"""BRO development panels. Speaker labels do not instantiate agents."""
import tkinter as tk
from tkinter import ttk
from camera import CameraPanel

SPEAKERS=("BRO","Sky","Cold","Monday","GRIT")

class Console:
    def __init__(self, app):
        self.app=app
        self.active=True
        self.messages=[]
        self.speaker=tk.StringVar(value="BRO")
        self.developer=tk.BooleanVar(value=True)
        self.camera_visible=tk.BooleanVar(value=False)
        bar=ttk.Frame(app.root,padding=(12,4));bar.pack(fill="x")
        ttk.Label(bar,text="Speaker:").pack(side="left")
        selector=ttk.Combobox(bar,textvariable=self.speaker,values=SPEAKERS,state="readonly",width=10)
        selector.pack(side="left",padx=6)
        selector.bind("<<ComboboxSelected>>",lambda _:app.log("Speaker selected: "+self.speaker.get()))
        ttk.Checkbutton(bar,text="Dev panels",variable=self.developer,command=self.toggle_dev).pack(side="left",padx=8)
        ttk.Checkbutton(bar,text="Camera preview",variable=self.camera_visible,command=self.toggle_camera).pack(side="left")
        self.session_button=ttk.Button(bar,text="End session",command=self.toggle_session)
        self.session_button.pack(side="right")
        self.session_status=tk.StringVar(value="Session active · local prototype")
        ttk.Label(bar,textvariable=self.session_status).pack(side="right",padx=10)
        self.panes=ttk.Panedwindow(app.root,orient="horizontal")
        self.panes.pack(fill="both",expand=True)
        self.face=ttk.Frame(self.panes)
        self.dev=ttk.Frame(self.panes,padding=8,width=310)
        self.panes.add(self.face,weight=4);self.panes.add(self.dev,weight=1)
        self.speech_frame=ttk.Frame(self.face,padding=8)
        self.speech_frame.pack(side="bottom",fill="x")
        heading=ttk.Frame(self.speech_frame);heading.pack(fill="x")
        ttk.Label(heading,text="Speech output",font=("Sans",12,"bold")).pack(side="left")
        ttk.Button(heading,text="Copy speech",command=self.copy_speech).pack(side="right")
        self.speech=self.text_box(self.speech_frame,4)
        ttk.Label(self.dev,text="BRO / DEVELOPMENT",font=("Sans",12,"bold")).pack(anchor="w")
        ttk.Label(self.dev,text="Keyboard + mouse: ready\nRotary: USB connection above\nJoystick: not connected",justify="left").pack(anchor="w",pady=8)
        ttk.Label(self.dev,text="Text output test (manual)",font=("Sans",10,"bold")).pack(anchor="w")
        self.draft=tk.Text(self.dev,height=3,width=28,wrap="word",bg="#13243a",fg="#d7fff6",insertbackground="white")
        self.draft.pack(fill="x",pady=5)
        self.publish=ttk.Button(self.dev,text="Display text as selected speaker",command=self.publish_draft)
        self.publish.pack(fill="x")
        ttk.Button(self.dev,text="BRO sample line",command=self.sample).pack(fill="x",pady=5)
        ttk.Label(self.dev,text="Activity log",font=("Sans",11,"bold")).pack(anchor="w",pady=(10,4))
        self.activity=self.text_box(self.dev,8,expand=True)
        ttk.Button(self.dev,text="Copy log",command=app.copy_log).pack(fill="x",pady=5)
        self.camera_feed=CameraPanel(self.dev,app)
        self.camera=self.camera_feed.frame
        self.show_output("BRO","Face online. Ready to build.",source="sample")

    def text_box(self,parent,height,expand=False):
        frame=ttk.Frame(parent);frame.pack(fill="both" if expand else "x",expand=expand)
        box=tk.Text(frame,height=height,width=28,wrap="word",bg="#060b15",fg="#c7d3e9",insertbackground="white",state="disabled")
        scroll=ttk.Scrollbar(frame,orient="vertical",command=box.yview)
        box.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right",fill="y");box.pack(side="left",fill="both",expand=True)
        return box

    def set_text(self,box,text):
        box.configure(state="normal");box.delete("1.0","end");box.insert("end",text)
        box.configure(state="disabled");box.see("end")

    def update_log(self):
        self.set_text(self.activity,"\n".join(self.app.logs))

    def show_output(self,speaker,text,source="output"):
        # Call on Tk's main thread when a conversation backend is connected.
        if not self.active:return False
        if speaker not in SPEAKERS:raise ValueError("Unknown speaker")
        text=str(text).strip()[:4000]
        if not text:return False
        self.messages.append(f"{speaker} [{source}]: {text}")
        self.messages=self.messages[-50:]
        self.set_text(self.speech,"\n\n".join(self.messages))
        if hasattr(self.app,"console"):self.app.log("Text displayed: "+speaker+" / "+source)
        return True

    def publish_draft(self):
        if self.show_output(self.speaker.get(),self.draft.get("1.0","end"),source="manual test"):
            self.draft.delete("1.0","end")

    def sample(self):
        self.show_output("BRO","Knob, eyes, tiny sparks. We are making progress.",source="sample")

    def copy_speech(self):
        self.app.root.clipboard_clear()
        self.app.root.clipboard_append("\n\n".join(self.messages))
        self.app.status.set("Speech copied")

    def toggle_dev(self):
        if self.developer.get():
            self.panes.add(self.dev,weight=1)
        else:
            self.camera_feed.stop()
            self.camera_visible.set(False);self.camera.pack_forget()
            self.panes.forget(self.dev)

    def toggle_camera(self):
        if self.camera_visible.get():
            if not self.developer.get():
                self.developer.set(True);self.toggle_dev()
            self.camera.pack(fill="x",pady=8)
            self.camera_feed.start()
        else:
            self.camera_feed.stop()
            self.camera.pack_forget()
        self.app.log("Camera panel "+("shown" if self.camera_visible.get() else "hidden"))

    def toggle_session(self):
        if self.active:
            self.camera_feed.stop()
            self.app.disconnect()
            self.active=False
            self.session_status.set("Session ended · USB released")
            self.session_button.configure(text="Start session")
            self.publish.configure(state="disabled")
            self.app.log("Session ended")
        else:
            self.active=True
            self.app.face.baseline=None
            self.session_status.set("Session active · connect USB to resume knob")
            self.session_button.configure(text="End session")
            self.publish.configure(state="normal")
            self.app.log("Session started")
