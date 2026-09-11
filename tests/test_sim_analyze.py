# -*- coding: utf-8 -*-
import json
import os
import tempfile
import unittest

from sim.analyze import analyze


class SimAnalyzeTests(unittest.TestCase):
    def _write(self, d, name, rows):
        with open(os.path.join(d, name), "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    def test_metrics(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as f:
                json.dump({"width": 320, "height": 320}, f)
            truths = []
            overlays = []
            for i in range(10):
                t = i / 100.0
                truths.append({"t": t, "frame": i, "targets": [
                    {"id": 1, "cls": 32, "x": 100 + i, "y": 150, "w": 30, "h": 30, "vx": 100, "vy": 0}
                ]})
                overlays.append({"t": t, "boxes": [[105 + i, 150, 30, 30]], "classes": [32],
                                 "input_w": 320, "input_h": 320, "track_id": 1})
            self._write(d, "truth.jsonl", truths)
            self._write(d, "overlay.jsonl", overlays)
            self._write(d, "events.jsonl", [
                {"t": 0.05, "kind": "click", "hit": True, "target_id": 1},
                {"t": 0.06, "kind": "click", "hit": False, "target_id": None},
            ])
            m = analyze(d, match_thresh=60.0)
            self.assertEqual(m["aligned_frames"], 10)
            self.assertEqual(m["detection_rate"], 1.0)
            self.assertAlmostEqual(m["mean_box_error_px"], 5.0, delta=0.5)
            self.assertEqual(m["clicks"], 2)
            self.assertEqual(m["hits"], 1)
            self.assertEqual(m["hit_rate"], 0.5)

    def test_empty_dir(self):
        with tempfile.TemporaryDirectory() as d:
            m = analyze(d)
            self.assertEqual(m["truth_frames"], 0)
            self.assertEqual(m["aligned_frames"], 0)


if __name__ == "__main__":
    unittest.main()
