import os, random, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from engine import Estimator

def warm(e, n=60, v=1.0, tds=500, seed=1):
    r = random.Random(seed)
    for _ in range(n): out = e.update(v + r.gauss(0, .03), tds)
    return out

class FailSafe(unittest.TestCase):
    def test_bad_sensor_reading_falls_back(self):
        e = Estimator(); warm(e)
        for tds in (0, 9999, None): self.assertEqual(e.update(1.0, tds)["status"], "FALLBACK")
    def test_missing_flow_falls_back(self): e = Estimator(); warm(e); self.assertEqual(e.update(None, 500)["status"], "FALLBACK")
    def test_implausible_flow_falls_back(self): e = Estimator(); warm(e); self.assertEqual(e.update(3.5, 500)["status"], "FALLBACK")
    def test_water_event_is_not_blamed_on_filter(self):
        e = Estimator(); warm(e)
        for _ in range(20): self.assertNotEqual(e.update(.78, 900, event=True)["status"], "ORDER NOW")
    def test_healthy_filter_never_alerts(self):
        e = Estimator(); r = random.Random(3)
        for d in range(700): self.assertNotEqual(e.update(1 - .00005 * d + r.gauss(0, .03), 300)["status"], "ORDER NOW")
    def test_degrading_filter_is_flagged_before_failure(self):
        e = Estimator(); r = random.Random(5); alert = None
        for d in range(400):
            h = 1 - .001 * d; st = e.update(h + r.gauss(0, .03), 900)["status"]
            if st == "ORDER NOW" and alert is None: alert = d
        self.assertIsNotNone(alert); self.assertLessEqual(alert, 150 - 10)   # failure line is crossed on day 150
if __name__ == "__main__": unittest.main(verbosity=2)
