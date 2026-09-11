"""合成靶场的目标运动仿真（服务器权威，供调试自瞄链路用）。

设计要点：
- 仿真状态完全在 Python 侧推进，浏览器只负责绘制；真值/命中都在服务器产生，
  便于离线比对与单元测试。
- 运动模型见 Simulation.MODES，支持变速反弹、随机布朗、消失/传送。
- 类别默认使用 COCO 的 sports ball (32)，也允许配置成其它可检测类别。
"""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass

DEFAULT_CLASS = 32  # COCO sports ball

SPRITE_BY_CLASS = {
    32: "ball",
    29: "frisbee",
}

BALL_COLORS = [
    (255, 214, 10),
    (255, 90, 60),
    (60, 180, 255),
    (120, 255, 120),
]


@dataclass
class Target:
    tid: int
    cls: int
    x: float
    y: float
    vx: float
    vy: float
    w: float
    h: float
    sprite: str = "ball"
    color: str = "0"
    alive: bool = True
    timer: float = 0.0
    orbit_cx: float = 0.0
    orbit_cy: float = 0.0
    orbit_radius: float = 0.0
    orbit_angle: float = 0.0

    def as_dict(self) -> dict:
        return {
            "id": self.tid,
            "cls": self.cls,
            "x": round(self.x, 2),
            "y": round(self.y, 2),
            "w": round(self.w, 2),
            "h": round(self.h, 2),
            "vx": round(self.vx, 2),
            "vy": round(self.vy, 2),
            "sprite": self.sprite,
            "color": self.color,
            "alive": self.alive,
        }


class Simulation:
    MODES = ("bounce", "brownian", "teleport", "blink", "orbit")
    SPRITES = ("ball", "frisbee")

    def __init__(
        self,
        width: int = 320,
        height: int = 320,
        mode: str = "bounce",
        count: int = 1,
        class_ids=None,
        seed=None,
        min_size: float = 30.0,
        max_size: float = 44.0,
        min_speed: float = 120.0,
        max_speed: float = 320.0,
        teleport_interval: float = 1.5,
        vanish_duration: float = 0.5,
        brownian_accel: float = 2600.0,
        blink_interval: float = 1.0,
        blink_dist: float = 0.0,
    ):
        self.width = int(width)
        self.height = int(height)
        self.mode = mode if mode in self.MODES else "bounce"
        self.count = max(1, int(count))
        self.class_ids = list(class_ids) if class_ids else [DEFAULT_CLASS]
        self.min_size = float(min_size)
        self.max_size = float(max_size)
        self.min_speed = float(min_speed)
        self.max_speed = float(max_speed)
        self.teleport_interval = float(teleport_interval)
        self.vanish_duration = float(vanish_duration)
        self.brownian_accel = float(brownian_accel)
        self.blink_interval = float(blink_interval)
        self.blink_dist = float(blink_dist)
        self.orbit_radius = 0.30 * min(self.width, self.height)
        self.orbit_w = 1.0
        self._rng = random.Random(seed)
        self._time = 0.0
        self._frame = 0
        self._next_id = 1
        self._targets: list[Target] = []
        self.blink_events: list[float] = []
        self._spawn_all()

    # ---------------- 生成 ----------------
    def _rand_speed_dir(self):
        ang = self._rng.uniform(0, 2 * math.pi)
        spd = self._rng.uniform(self.min_speed, self.max_speed)
        return math.cos(ang) * spd, math.sin(ang) * spd

    def _rand_size(self):
        s = self._rng.uniform(self.min_size, self.max_size)
        return s, s

    def _spawn(self, tid: int, cls: int) -> Target:
        w, h = self._rand_size()
        hw, hh = w / 2, h / 2
        x = self._rng.uniform(hw, self.width - hw)
        y = self._rng.uniform(hh, self.height - hh)
        vx, vy = self._rand_speed_dir()
        t = Target(
            tid=tid,
            cls=int(cls),
            x=x,
            y=y,
            vx=vx,
            vy=vy,
            w=w,
            h=h,
            sprite=SPRITE_BY_CLASS.get(int(cls), "ball"),
            color=str(self._rng.randrange(len(BALL_COLORS))),
            alive=True,
            timer=(self.blink_interval if self.mode == "blink" else self.teleport_interval),
        )
        if self.mode == "orbit":
            r = self.orbit_radius
            t.orbit_radius = r
            t.orbit_cx = self._rng.uniform(r, self.width - r)
            t.orbit_cy = self._rng.uniform(r, self.height - r)
            t.orbit_angle = self._rng.uniform(0, 2 * math.pi)
            t.x = t.orbit_cx + r * math.cos(t.orbit_angle)
            t.y = t.orbit_cy + r * math.sin(t.orbit_angle)
        return t

    def _spawn_all(self):
        self._targets = []
        for _ in range(self.count):
            cls = self.class_ids[len(self._targets) % len(self.class_ids)]
            self._targets.append(self._spawn(self._next_id, cls))
            self._next_id += 1

    # ---------------- 推进 ----------------
    def _reflect(self, t: Target):
        hw, hh = t.w / 2, t.h / 2
        if t.x < hw:
            t.x = hw
            t.vx = abs(t.vx)
        elif t.x > self.width - hw:
            t.x = self.width - hw
            t.vx = -abs(t.vx)
        if t.y < hh:
            t.y = hh
            t.vy = abs(t.vy)
        elif t.y > self.height - hh:
            t.y = self.height - hh
            t.vy = -abs(t.vy)

    def _respawn(self, t: Target):
        w, h = self._rand_size()
        t.w, t.h = w, h
        t.x = self._rng.uniform(w / 2, self.width - w / 2)
        t.y = self._rng.uniform(h / 2, self.height - h / 2)
        t.vx, t.vy = self._rand_speed_dir()
        t.alive = True
        t.timer = self.teleport_interval

    def step(self, dt: float):
        dt = max(0.0, min(float(dt), 0.1))
        self._time += dt
        self._frame += 1
        for t in self._targets:
            if not t.alive:
                t.timer -= dt
                if t.timer <= 0:
                    self._respawn(t)
                continue
            if self.mode == "orbit":
                r = t.orbit_radius or self.orbit_radius
                t.orbit_angle += self.orbit_w * dt
                ang = t.orbit_angle
                t.x = t.orbit_cx + r * math.sin(ang)
                t.y = t.orbit_cy + 0.4 * r * math.sin(2 * ang)
                t.vx = r * self.orbit_w * math.cos(ang)
                t.vy = 0.8 * r * self.orbit_w * math.cos(2 * ang)
                continue
            if self.mode == "brownian":
                t.vx += self._rng.uniform(-1, 1) * self.brownian_accel * dt
                t.vy += self._rng.uniform(-1, 1) * self.brownian_accel * dt
                speed = math.hypot(t.vx, t.vy)
                if speed > self.max_speed and speed > 0:
                    k = self.max_speed / speed
                    t.vx *= k
                    t.vy *= k
                elif speed < self.min_speed * 0.5 and speed > 0:
                    k = (self.min_speed * 0.5) / speed
                    t.vx *= k
                    t.vy *= k
                t.x += t.vx * dt
                t.y += t.vy * dt
                self._reflect(t)
            else:
                t.x += t.vx * dt
                t.y += t.vy * dt
                self._reflect(t)
                if self.mode == "teleport":
                    t.timer -= dt
                    if t.timer <= 0:
                        t.alive = False
                        t.timer = self.vanish_duration
                elif self.mode == "blink":
                    t.timer -= dt
                    if t.timer <= 0:
                        self._blink(t)
                        t.timer = self.blink_interval
        return self.snapshot()

    def _blink(self, t: Target):
        """瞬间把目标传送到随机位置（可要求最小跳跃距离）。"""
        w, h = self._rand_size()
        t.w, t.h = w, h
        nx = self._rng.uniform(w / 2, self.width - w / 2)
        ny = self._rng.uniform(h / 2, self.height - h / 2)
        if self.blink_dist > 0:
            for _ in range(12):
                if math.hypot(nx - t.x, ny - t.y) >= self.blink_dist:
                    break
                nx = self._rng.uniform(w / 2, self.width - w / 2)
                ny = self._rng.uniform(h / 2, self.height - h / 2)
        t.x, t.y = nx, ny
        t.vx, t.vy = self._rand_speed_dir()
        self.blink_events.append(time.time())

    # ---------------- 输出 ----------------
    def snapshot(self) -> dict:
        return {
            "frame": self._frame,
            "targets": [t.as_dict() for t in self._targets],
        }

    def hit_test(self, x: float, y: float):
        for t in self._targets:
            if not t.alive:
                continue
            if abs(x - t.x) <= t.w / 2 and abs(y - t.y) <= t.h / 2:
                return t
        return None

    def center_hit(self):
        return self.hit_test(self.width / 2, self.height / 2)

    def pan(self, dx: float, dy: float, sens: float = 1.0):
        """鼠标相对移动 -> 视角平移（目标屏幕坐标反向移动），模拟游戏相机。"""
        ox = dx * sens
        oy = dy * sens
        if ox == 0 and oy == 0:
            return
        for t in self._targets:
            if self.mode == "orbit":
                t.orbit_cx -= ox
                t.orbit_cy -= oy
                r = t.orbit_radius or self.orbit_radius
                t.x = t.orbit_cx + r * math.sin(t.orbit_angle)
                t.y = t.orbit_cy + 0.4 * r * math.sin(2 * t.orbit_angle)
            else:
                t.x -= ox
                t.y -= oy
                self._reflect(t)

    # ---------------- 运行时控制 ----------------
    def set_mode(self, mode: str):
        if mode in self.MODES:
            self.mode = mode
            for t in self._targets:
                t.timer = self.teleport_interval

    def set_count(self, count: int):
        count = max(1, min(8, int(count)))
        if count == self.count:
            return
        self.count = count
        self._spawn_all()

    def set_speed(self, min_speed: float, max_speed: float):
        self.min_speed = max(10.0, float(min_speed))
        self.max_speed = max(self.min_speed + 1.0, float(max_speed))

    def set_target_speed(self, speed: float):
        """把所有目标的速率设为目标值（保留方向），并同步速度范围。"""
        speed = max(10.0, float(speed))
        self.min_speed = speed * 0.8
        self.max_speed = speed
        self.orbit_w = speed / max(1.0, self.orbit_radius)
        for t in self._targets:
            sp = math.hypot(t.vx, t.vy)
            if sp < 1e-6:
                t.vx, t.vy = self._rand_speed_dir()
            else:
                k = speed / sp
                t.vx *= k
                t.vy *= k
