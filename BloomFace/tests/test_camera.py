import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
import unittest
from unittest.mock import patch
import queue
import threading
from types import SimpleNamespace
from camera import capture_worker

class FakeCapture:
    def __init__(self,opened):self.opened=opened;self.released=False;self.reads=0
    def isOpened(self):return self.opened
    def set(self,*args):pass
    def read(self):
        self.reads+=1
        return (self.reads==1,SimpleNamespace(shape=(1,1,3),tobytes=lambda:bytes([1,2,3])))
    def release(self):self.released=True

class CameraTests(unittest.TestCase):
    def backend(self,caps):
        return SimpleNamespace(VideoCapture=lambda *args:caps.pop(0),CAP_V4L2=1,CAP_ANY=0,CAP_PROP_FRAME_WIDTH=3,CAP_PROP_FRAME_HEIGHT=4,COLOR_BGR2RGB=1,cvtColor=lambda f,*_:f,resize=lambda f,*_:f)
    def test_unreadable_devices_released(self):
        cap=FakeCapture(False);q=queue.Queue()
        with patch.dict(sys.modules,cv2=self.backend([cap])),patch('camera.candidates',return_value=['/dev/video0']):capture_worker(q,threading.Event(),'Auto')
        self.assertTrue(cap.released);self.assertEqual(q.get()[0],'error')
    def test_preview_and_unplug_release(self):
        cap=FakeCapture(True);q=queue.Queue()
        with patch.dict(sys.modules,cv2=self.backend([cap])),patch('camera.candidates',return_value=['/dev/video0']):capture_worker(q,threading.Event(),'Auto')
        self.assertTrue(cap.released)
        self.assertEqual(q.get()[0],'status')
        kind,frame=q.get();self.assertEqual(kind,'frame');self.assertTrue(frame.startswith(b'P6\n'))
        self.assertIn('disconnected',q.get()[1])
    def test_stopped_before_detection(self):
        event=threading.Event();event.set();q=queue.Queue()
        with patch.dict(sys.modules,cv2=self.backend([])),patch('camera.candidates',return_value=['/dev/video0']):capture_worker(q,event,'Auto')
        self.assertTrue(q.empty())
