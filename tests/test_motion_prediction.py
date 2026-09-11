# -*- coding: utf-8 -*-
"""AimPipeline 移动预测（Kalman lead）接线回归测试。

历史缺陷：KalmanPredictor2D 虽然完整实现，但从未被 update/predict，
实际 lead 由手搓 EMA + 猜测增益给出，锁定后速度估计会失稳/塌缩。
"""
import unittest
import unittest.mock as mock

from aim.aim_pipeline import AimPipeline


class MotionPredictionTests(unittest.TestCase):
    def test_kalman_velocity_matches_true_speed(self):
        p = AimPipeline()
        p.kalman_enabled = True
        p.predict_gain = 0.0  # 关闭自运动补偿，单独验证 Kalman 滤波
        p._prev_pid_raw = (0.0, 0.0)
        fake = [1000.0]
        with mock.patch("aim.aim_pipeline.time.time", lambda: fake[0]):
            x0, y0 = 100.0, 200.0
            for i in range(40):
                fake[0] += 0.01  # 10ms 一帧
                x = x0 + 20.0 * i  # 20px/帧 = 2000px/s
                p._prev_aim_time = fake[0] - 0.01
                p._update_motion_prediction(1, x, y0, fake[0])
        self.assertGreater(p._est_vx, 1500.0)
        self.assertAlmostEqual(p._est_vx, 2000.0, delta=400.0)

    def test_fallback_ema_when_no_track_id(self):
        p = AimPipeline()
        p.predict_gain = 0.0
        p._prev_pid_raw = (0.0, 0.0)
        p._prev_aim_pos = (100.0, 200.0)
        p._prev_aim_time = 1000.0
        for i in range(1, 30):
            t = 1000.0 + i * 0.01
            x = 100.0 + 20.0 * i
            p._update_motion_prediction(None, x, 200.0, t)
            p._prev_aim_pos = (x, 200.0)
            p._prev_aim_time = t
        self.assertGreater(p._est_vx, 1500.0)

    def test_reset_clears_state(self):
        p = AimPipeline()
        p._est_vx = 123.0
        p._lead_x = 5.0
        p._prev_pid_raw = (1.0, 2.0)
        p._reset_motion_prediction()
        self.assertEqual(p._est_vx, 0.0)
        self.assertEqual(p._lead_x, 0.0)
        self.assertEqual(p._prev_pid_raw, (0.0, 0.0))
        self.assertIsNone(p._prev_aim_time)

    def test_lead_params_read_from_key_config(self):
        p = AimPipeline()
        key = {
            "min_lead_speed": 123.0, "max_lead": 77.0, "lead_smooth": 0.42,
            "class_aim_positions": {}, "min_position_offset": 0.0, "move_deadzone": 0.0,
            "target_switch_delay": 0, "target_reference_class": 0,
            "large_target_threshold": 0.055, "large_target_boost": 1.12,
        }
        cfg = {
            "small_target_enhancement": {}, "target_id_lock_enabled": True,
            "target_sticky_pixels": 40.0, "target_lock_ms": 150.0, "kalman": {},
        }
        p._get_aim_params(cfg, key)
        self.assertEqual(p.min_lead_speed, 123.0)
        self.assertEqual(p.max_lead, 77.0)
        self.assertAlmostEqual(p._lead_smooth, 0.42)


if __name__ == "__main__":
    unittest.main()
