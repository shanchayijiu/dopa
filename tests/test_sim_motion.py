# -*- coding: utf-8 -*-
import unittest

from sim.motion import Simulation


class SimMotionTests(unittest.TestCase):
    def test_bounce_stays_in_bounds(self):
        sim = Simulation(width=320, height=320, mode="bounce", count=3, seed=1)
        for _ in range(2000):
            snap = sim.step(1 / 120.0)
        for t in snap["targets"]:
            self.assertGreaterEqual(t["x"], t["w"] / 2 - 1e-6)
            self.assertLessEqual(t["x"], 320 - t["w"] / 2 + 1e-6)
            self.assertGreaterEqual(t["y"], t["h"] / 2 - 1e-6)
            self.assertLessEqual(t["y"], 320 - t["h"] / 2 + 1e-6)

    def test_brownian_speed_clamped(self):
        sim = Simulation(width=320, height=320, mode="brownian", count=2, seed=2)
        snap = None
        for _ in range(800):
            snap = sim.step(1 / 120.0)
        for t in snap["targets"]:
            sp = (t["vx"] ** 2 + t["vy"] ** 2) ** 0.5
            self.assertLessEqual(sp, sim.max_speed + 1e-3)
            self.assertGreaterEqual(sp, sim.min_speed * 0.5 - 1e-3)

    def test_teleport_toggles_alive(self):
        sim = Simulation(mode="teleport", count=1, seed=3, teleport_interval=0.1, vanish_duration=0.1)
        seen_dead = False
        for _ in range(600):
            snap = sim.step(1 / 120.0)
            if not snap["targets"][0]["alive"]:
                seen_dead = True
        self.assertTrue(seen_dead)

    def test_pan_moves_target_opposite(self):
        sim = Simulation(width=320, height=320, count=1, seed=4)
        t = sim._targets[0]
        t.x, t.y, t.w, t.h, t.alive = 160.0, 160.0, 40.0, 40.0, True
        sim.pan(10.0, 0.0, 1.0)
        self.assertAlmostEqual(t.x, 150.0, delta=1e-6)
        self.assertAlmostEqual(t.y, 160.0, delta=1e-6)

    def test_center_hit(self):
        sim = Simulation(width=320, height=320, count=1, seed=5)
        t = sim._targets[0]
        t.x, t.y, t.w, t.h, t.alive = 160.0, 160.0, 40.0, 40.0, True
        self.assertIsNotNone(sim.center_hit())
        t.x = 20.0
        t.y = 20.0
        self.assertIsNone(sim.center_hit())

    def test_set_count_respawns(self):
        sim = Simulation(width=320, height=320, count=1, seed=6)
        sim.set_count(4)
        self.assertEqual(len(sim.snapshot()["targets"]), 4)

    def test_blink_jumps_and_logs(self):
        sim = Simulation(width=320, height=320, mode="blink", count=1, seed=11,
                         blink_interval=0.2, blink_dist=80.0)
        prev = sim.snapshot()["targets"][0]
        max_jump = 0.0
        for _ in range(240):
            snap = sim.step(1 / 120.0)
            t = snap["targets"][0]
            jump = ((t["x"] - prev["x"]) ** 2 + (t["y"] - prev["y"]) ** 2) ** 0.5
            max_jump = max(max_jump, jump)
            prev = t
        self.assertGreater(max_jump, 80.0)
        self.assertGreaterEqual(len(sim.blink_events), 3)


if __name__ == "__main__":
    unittest.main()
