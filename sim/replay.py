"""闭环回放 harness：用可控真值轨迹驱动 AimPipeline，量化动态追踪。

与靶场一致地模拟“自运动”：每帧把 PID 输出当作相机平移量，反向加到目标屏幕
坐标上，形成真实闭环。默认 PID 增益取自项目 cfg 中的实机值（见
core/mixins/config.refresh_controller_params），避免用构造函数默认值造成假象。
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

import numpy as np

import aim.aim_pipeline as aim_pipeline
from .metrics import lock_metrics

# 与 cfg.json / refresh_controller_params 对齐的实机 PID 参数
DEFAULT_KEY = {
    "pid_kp_x": 0.2, "pid_kp_y": 0.2,
    "pid_ki_x": 2.0, "pid_ki_y": 2.0,
    "pid_kd_x": 0.003, "pid_kd_y": 0.003,
    "pid_integral_limit_x": 5.0, "pid_integral_limit_y": 5.0,
    "smooth_x": 1.0, "smooth_y": 1.0, "smooth_deadzone": 0.0,
    "pid_error_filter_alpha": 0.0, "pid_vel_filter_alpha": 0.0,
    "min_position_offset": 0.0, "move_deadzone": 0.0,
    "class_aim_positions": {}, "confidence_threshold": 0.5, "iou_t": 1.0,
    "aim_bot_position": 0.5, "aim_bot_position2": 0.5,
}

DEFAULT_KALMAN = {
    "enabled": True, "predict_frames": 5, "predict_gain": 1.0,
    "process_noise": 0.5, "measurement_noise": 15.0,
}


def configure_pipeline(pipeline, key=None):
    key = key or DEFAULT_KEY
    p = pipeline.pid
    p.set_pid_params(
        kp=[key["pid_kp_x"], key["pid_kp_y"]],
        ki=[key["pid_ki_x"], key["pid_ki_y"]],
        kd=[key["pid_kd_x"], key["pid_kd_y"]],
    )
    p.set_windup_guard([key["pid_integral_limit_x"], key["pid_integral_limit_y"]])
    p.set_smooth_params(key["smooth_x"], key["smooth_y"], key["smooth_deadzone"], 1.0)
    p.set_error_filter(key["pid_error_filter_alpha"])
    p.set_vel_filter(key["pid_vel_filter_alpha"])
    pipeline.tracker_enabled = bool(key.get("tracker_enabled", True))
    pipeline.target_id_lock_enabled = bool(key.get("target_id_lock_enabled", True))


def default_cfg(use_kalman=True, **overrides):
    cfg = {
        "small_target_enhancement": {},
        "target_id_lock_enabled": True,
        "target_sticky_pixels": 40.0,
        "target_lock_ms": 150.0,
        "kalman": dict(DEFAULT_KALMAN, enabled=bool(use_kalman)),
    }
    cfg.update(overrides)
    return cfg


@dataclass
class ReplayResult:
    errors: list = field(default_factory=list)
    id_switches: int = 0
    lost_frames: int = 0
    fps: float = 100.0
    vx: float = 0.0
    use_kalman: bool = True

    def metrics(self, **kw):
        return lock_metrics(self.errors, self.fps, **kw)


def _clamp_speed(vx, vy, lo, hi):
    sp = math.hypot(vx, vy)
    if sp <= 1e-9:
        return vx, vy
    if sp > hi:
        k = hi / sp
        return vx * k, vy * k
    if sp < lo:
        k = lo / sp
        return vx * k, vy * k
    return vx, vy


def run_replay(
    vx=150.0,
    vy=0.0,
    *,
    motion="linear",
    duration=5.0,
    fps=100.0,
    playfield=320.0,
    target_size=30.0,
    start=(100.0, 160.0),
    use_kalman=True,
    sens=1.0,
    key=None,
    cfg=None,
    brownian_accel=1500.0,
    teleport_interval=1.2,
    vanish_duration=0.2,
    seed=0,
    pipeline=None,
):
    """跑一段闭环回放，返回逐帧误差等。"""
    key = key or DEFAULT_KEY
    cfg = cfg or default_cfg(use_kalman)
    p = pipeline or aim_pipeline.AimPipeline()
    configure_pipeline(p, key)
    p.kalman_enabled = bool(use_kalman)

    rng = random.Random(seed)
    clock = [1000.0]
    orig_time = aim_pipeline.time.time
    aim_pipeline.time.time = lambda: clock[0]

    center = (playfield / 2.0, playfield / 2.0)
    dt = 1.0 / float(fps)
    world = [float(start[0]), float(start[1])]
    vel = [float(vx), float(vy)]
    cam = [0.0, 0.0]
    result = ReplayResult(fps=fps, vx=float(vx), use_kalman=bool(use_kalman))
    prev_id = None
    tp_timer = teleport_interval
    hidden_until = -1.0

    try:
        total = int(duration * fps)
        for i in range(total):
            clock[0] += dt
            t = i * dt

            if motion == "brownian":
                vel[0] += rng.uniform(-1, 1) * brownian_accel * dt
                vel[1] += rng.uniform(-1, 1) * brownian_accel * dt
                base = max(60.0, math.hypot(vx, vy))
                vel[0], vel[1] = _clamp_speed(vel[0], vel[1], base * 0.4, base * 1.6)
            world[0] += vel[0] * dt
            world[1] += vel[1] * dt

            hidden = False
            if motion == "teleport":
                tp_timer -= dt
                if hidden_until >= 0.0:
                    hidden = t < hidden_until
                    if not hidden:
                        hidden_until = -1.0
                        tp_timer = teleport_interval
                elif tp_timer <= 0.0:
                    hidden = True
                    hidden_until = t + vanish_duration

            sx = world[0] - cam[0]
            sy = world[1] - cam[1]
            if hidden:
                boxes = np.zeros((0, 4), dtype=np.float32)
            else:
                boxes = np.array([[sx, sy, target_size, target_size]], dtype=np.float32)

            payload = {
                "frame_id": i,
                "boxes": boxes,
                "class_ids": [0] if len(boxes) else [],
                "input_w": float(playfield),
                "input_h": float(playfield),
            }
            out = p.step_frame(payload, key, cfg, center, 0.0, 0.0, 0.0, playfield * playfield)

            result.errors.append(math.hypot(sx - center[0], sy - center[1]))
            if getattr(p, "_last_selected_target_id", None) is None:
                result.lost_frames += 1
            if out:
                cam[0] += out[0] * sens
                cam[1] += out[1] * sens
            tid = getattr(p, "_last_output_target_id", None)
            if tid is not None and prev_id is not None and tid != prev_id:
                result.id_switches += 1
            if tid is not None:
                prev_id = tid
    finally:
        aim_pipeline.time.time = orig_time

    return result
