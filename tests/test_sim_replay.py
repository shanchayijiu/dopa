# -*- coding: utf-8 -*-
"""动态目标追踪闭环回放回归（M0）。

阈值基于实机 PID 增益（sim.replay.DEFAULT_KEY）下的基线，留有余量，
用于卡住“追踪/预测被改坏”的回归，而非追求极限精度。
"""
import unittest

from sim.metrics import speed_sweep_report
from sim.replay import run_replay


class DynamicTrackReplayTests(unittest.TestCase):
    def test_linear_150_locks(self):
        r = run_replay(150.0, duration=4.0)
        m = r.metrics()
        self.assertTrue(m["locked"], m)
        self.assertLessEqual(m["e_med"], 12.0, m)
        self.assertEqual(r.id_switches, 0)

    def test_linear_350_locks(self):
        r = run_replay(350.0, duration=4.0)
        m = r.metrics()
        self.assertTrue(m["locked"], m)
        self.assertLessEqual(m["e_med"], 12.0, m)
        self.assertEqual(r.id_switches, 0)

    def test_linear_550_locks(self):
        r = run_replay(550.0, duration=4.0)
        m = r.metrics()
        self.assertTrue(m["locked"], m)
        self.assertLessEqual(m["e_med"], 18.0, m)
        self.assertEqual(r.id_switches, 0)

    def test_kalman_helps_high_speed(self):
        fast = run_replay(800.0, duration=4.0, use_kalman=True).metrics()["e_med"]
        slow = run_replay(800.0, duration=4.0, use_kalman=False).metrics()["e_med"]
        self.assertLessEqual(fast, slow, f"kalman={fast} nokalman={slow}")

    def test_teleport_relocks(self):
        r = run_replay(250.0, motion="teleport", duration=6.0, seed=1)
        m = r.metrics()
        self.assertTrue(m["locked"], m)
        self.assertLessEqual(r.id_switches, 8, r.id_switches)

    def test_brownian_runs_and_tracks(self):
        r = run_replay(300.0, motion="brownian", duration=5.0, seed=2)
        self.assertGreater(len(r.errors), 0)
        self.assertLessEqual(r.metrics()["e_p95"], 45.0, r.metrics())

    def test_speed_sweep_kalman_extends_vmax(self):
        speeds = [300.0, 500.0, 600.0, 800.0]

        def sweep(kalman):
            res = [(v, run_replay(v, duration=4.0, use_kalman=kalman).metrics()) for v in speeds]
            return speed_sweep_report(res)[1]

        vmax_on = sweep(True)
        vmax_off = sweep(False)
        self.assertIsNotNone(vmax_on)
        self.assertGreaterEqual(vmax_on, 700.0, f"kalman vmax={vmax_on}")
        self.assertGreater(vmax_on, vmax_off, f"on={vmax_on} off={vmax_off}")


if __name__ == "__main__":
    unittest.main()
