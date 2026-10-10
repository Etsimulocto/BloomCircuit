import unittest

from happyjarz_art_studio import HEIGHT, PIXELS, STAMP_NAMES, WIDTH, circle_points, pack_xbm, stamp_points


class PixelArtHelpersTest(unittest.TestCase):
    def test_xbm_is_1024_bytes_and_packs_lsb_first_by_row(self):
        pixels = [0] * PIXELS
        pixels[0] = 1
        pixels[7] = 1
        pixels[8] = 1
        pixels[WIDTH] = 1
        packed = pack_xbm(pixels)
        self.assertEqual(len(packed), 1024)
        self.assertEqual(packed[0], 0b10000001)
        self.assertEqual(packed[1], 0b00000001)
        self.assertEqual(packed[16], 0b00000001)

    def test_circle_is_clipped_and_symmetric(self):
        points = circle_points(64, 32, 8)
        self.assertIn((72, 32), points)
        self.assertIn((56, 32), points)
        self.assertIn((64, 24), points)
        self.assertIn((64, 40), points)
        self.assertTrue(all(0 <= x < WIDTH and 0 <= y < HEIGHT for x, y in points))
        self.assertEqual({(x - 64, y - 32) for x, y in points},
                         {(-(x - 64), y - 32) for x, y in points})

    def test_every_stamp_draws_a_clipped_shape(self):
        for name in STAMP_NAMES:
            with self.subTest(name=name):
                points = stamp_points(name, 64, 32, 1)
                self.assertTrue(points)
                self.assertTrue(all(0 <= x < WIDTH and 0 <= y < HEIGHT for x, y in points))
                larger = stamp_points(name, 64, 32, 3)
                self.assertGreater(len(larger), len(points))

    def test_stamps_clip_at_canvas_edge(self):
        for name in STAMP_NAMES:
            points = stamp_points(name, 0, 0, 3)
            self.assertTrue(all(0 <= x < WIDTH and 0 <= y < HEIGHT for x, y in points))


if __name__ == "__main__":
    unittest.main()
