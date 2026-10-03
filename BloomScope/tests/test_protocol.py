import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("bloomscope", Path(__file__).parents[1] / "bloomscope.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ProtocolTests(unittest.TestCase):
    def test_divider_and_calibration(self):
        self.assertAlmostEqual(module.voltage(1650), 3.3)
        self.assertAlmostEqual(module.voltage(2500), 5.0)
        self.assertAlmostEqual(module.voltage(1600, 3.3 / 3.2), 3.3)

    def test_partial_serial_record_is_not_a_capture(self):
        with self.assertRaises(ValueError):
            module.decode('{"type":"capture",')

    def test_capture_preserves_actual_timestamps(self):
        d = module.decode('{"type":"capture","mode":"SCOPE","t_us":[0,1003,2001],"values":[0,1650,2500]}')
        self.assertEqual(d["t_us"], [0, 1003, 2001])

    def test_bad_captures_rejected(self):
        for line in (
            '{"type":"capture","t_us":[0,1],"values":[1]}',
            '{"type":"capture","t_us":[0,0],"values":[1,2]}',
            '{"type":"capture","t_us":[0,1],"values":[1,NaN]}',
            '[1,2]',
        ):
            with self.subTest(line=line), self.assertRaises(ValueError):
                module.decode(line)

    def test_pwm_idle_does_not_divide_by_zero(self):
        class DummyReadout:
            def set(self, text):
                self.text = text
            def get(self):
                return self.text
        app = object.__new__(module.App)
        app.readout = DummyReadout()
        app.log = lambda *args, **kwargs: None
        app.record({"type":"pwm", "valid":False, "period_us":0, "state":0})
        self.assertIn("No recent pulses", app.readout.text)


if __name__ == "__main__":
    unittest.main()
