# -*- coding: utf-8 -*-
"""ByteTrack 速度估计回归测试。

历史缺陷：STrack.update() 在 predict() 之后用“预测中心”去测量位移，
导致匀速目标的 EMA 速度稳定收敛到真值的一半。速度又被用于下一次
predict()，使轨迹外推持续偏慢、IoU 关联在快速目标上退化。
"""
import unittest

import numpy as np

from aim.bytetrack import ByteTracker


def _det(cx, cy=240.0, w=40.0, h=80.0):
    return np.array([[cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]], dtype=np.float32)


class ByteTrackVelocityTests(unittest.TestCase):
    def test_constant_velocity_converges_to_true_value(self):
        tracker = ByteTracker(track_thresh=0.5, match_thresh=0.3, track_buffer=30)
        true_vx = 20.0
        last_vel = None
        for f in range(30):
            cx = 100.0 + true_vx * f
            tracks = tracker.update(
                _det(cx),
                np.array([1.0], dtype=np.float32),
                np.array([0], dtype=np.int32),
            )
            self.assertEqual(len(tracks), 1)
            # 轨迹必须保持同一 id
            self.assertEqual(tracks[0].track_id, 1)
            last_vel = tracks[0].velocity
        # 旧实现会收敛到 10（真值一半），修复后应逼近 20
        self.assertGreater(last_vel[0], 18.0)
        self.assertAlmostEqual(last_vel[0], true_vx, delta=2.0)
        self.assertAlmostEqual(last_vel[1], 0.0, delta=1e-3)

    def test_velocity_sign_negative_direction(self):
        tracker = ByteTracker(track_thresh=0.5, match_thresh=0.3, track_buffer=30)
        for f in range(30):
            cx = 400.0 - 15.0 * f
            tracks = tracker.update(
                _det(cx),
                np.array([1.0], dtype=np.float32),
                np.array([0], dtype=np.int32),
            )
        self.assertLess(tracks[0].velocity[0], -13.0)

    def test_speed_normalized_after_gap(self):
        tracker = ByteTracker(track_thresh=0.5, match_thresh=0.3, track_buffer=30)
        # 先稳定跟踪一段
        for f in range(5):
            tracker.update(
                _det(100.0 + 10.0 * f),
                np.array([1.0], dtype=np.float32),
                np.array([0], dtype=np.int32),
            )
        # 目标消失 5 帧（更新 None 推进 frame_id）
        for _ in range(5):
            tracker.update(None)
        # 重新出现在前方 150px，跨 6 帧 → 约 25px/帧
        tracks = tracker.update(
            _det(100.0 + 10.0 * 4 + 150.0),
            np.array([1.0], dtype=np.float32),
            np.array([0], dtype=np.int32),
        )
        self.assertEqual(len(tracks), 1)
        # 不应把 150px 全部当成单帧位移
        self.assertLess(tracks[0].velocity[0], 150.0)


if __name__ == "__main__":
    unittest.main()
