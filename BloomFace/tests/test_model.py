import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).parents[1]))
from model import FaceState,MOODS


def packet(q=0,taps=0,holds=0,session=1):
    return dict(session=session,quarters=q,taps=taps,holds=holds)


class ModelTests(unittest.TestCase):
    def test_initial_packet_does_not_replay_old_actions(self):
        f=FaceState();self.assertEqual(f.ingest(packet(24,4,3)),[])
        self.assertEqual((f.mood,f.control,f.surprise),(0,0,0))

    def test_quadrature_bounce_cancels_and_full_detent_moves(self):
        f=FaceState();f.ingest(packet())
        f.ingest(packet(1));f.ingest(packet(0));self.assertEqual(f.mood,0)
        f.ingest(packet(4));self.assertEqual(f.mood,1)
        f.ingest(packet(4));self.assertEqual(f.mood,1)
        f.ingest(packet(0));self.assertEqual(f.mood,0)

    def test_wrap_and_reverse(self):
        f=FaceState();f.turn(-1);self.assertEqual(f.mood,len(MOODS)-1)
        f.reverse=True;f.turn(-1);self.assertEqual(f.mood,0)

    def test_limits(self):
        f=FaceState();f.tap();f.turn(100);self.assertEqual(f.gaze,1)
        f.turn(-100);self.assertEqual(f.gaze,-1)
        f.tap();f.turn(100);self.assertEqual(f.energy,1)
        f.turn(-100);self.assertEqual(f.energy,0)
        f.tap();f.turn(100);self.assertTrue(0<=f.hue<1)

    def test_click_hold_and_reboot(self):
        f=FaceState();f.ingest(packet());f.ingest(packet(taps=1));self.assertEqual(f.control,1)
        f.ingest(packet(taps=1,holds=1));self.assertEqual(f.surprise,1)
        f.ingest(packet(session=2));self.assertEqual(f.control,1)
        self.assertEqual(f.surprise,1)

    def test_two_edges_per_detent(self):
        f=FaceState();f.detent=2;f.ingest(packet());f.ingest(packet(2));self.assertEqual(f.mood,1)

    def test_malformed_counters(self):
        with self.assertRaises(ValueError):FaceState().ingest(packet(q="4"))


if __name__=="__main__":unittest.main()
