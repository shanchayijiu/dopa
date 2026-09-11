"""虚拟游戏：单机测试用的"游戏端"。

职责：
- 维护球的无规则运动（复用 sim.motion.Simulation）与相机平移；
- 收到鼠标位移(move)时按灵敏度平移视角（模拟游戏相机）；
- 渲染 320x320 BGR 帧供原生 pipeline 抓取；可选小窗口实时显示；
- 记录每帧观测用于指标。

它只替换"帧源"和"鼠标输出"两个 I/O，不改动任何原生算法。
"""
from __future__ import annotations

import math
import os
import threading
import time

import cv2
import numpy as np

from .motion import Simulation

_shared = None


def set_shared_game(game):
    global _shared
    _shared = game


def get_shared_game():
    return _shared


def ensure_window(name, size=(480, 480)):
    """创建/置顶一个可缩放的 OpenCV 窗口，便于肉眼观察。"""
    try:
        cv2.namedWindow(name, cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO)
        cv2.resizeWindow(name, size[0], size[1])
        cv2.setWindowProperty(name, cv2.WND_PROP_TOPMOST, 1.0)
    except Exception:
        pass


def draw_ball(frame, x, y, r=24):
    cv2.circle(frame, (int(x), int(y)), int(r), (60, 200, 120), -1)
    cv2.circle(frame, (int(x), int(y)), int(r), (15, 80, 35), 3)
    cv2.circle(frame, (int(x - r * 0.25), int(y - r * 0.3)), max(3, int(r * 0.35)),
               (120, 235, 170), -1)
    cv2.ellipse(frame, (int(x), int(y)), (int(r), int(r)), 0, 25, 155, (255, 255, 255), 5)
    cv2.ellipse(frame, (int(x), int(y)), (int(r), int(r)), 0, 205, 335, (255, 255, 255), 5)


class VirtualGame:
    def __init__(self, width=320, height=320, *, mode="bounce", count=1,
                 class_ids=(32, 29), sens=1.0, show=True, window="virtual range",
                 record=True, out_dir=None):
        self.width = int(width)
        self.height = int(height)
        self.sens = float(sens)
        self.show = bool(show)
        self.window = window
        self.record = bool(record)
        self.out_dir = out_dir
        self.sim = Simulation(width=self.width, height=self.height, mode=mode,
                              count=count, class_ids=list(class_ids))
        self.camera = [0.0, 0.0]
        self._lock = threading.Lock()
        self._frame = None
        self._running = False
        self._thread = None
        self._samples = []  # (t, [(tid, x, y)])

    # ---------- 供 app 调用 ----------
    def move(self, dx, dy):
        try:
            with self._lock:
                self.sim.pan(float(dx), float(dy), self.sens)
        except Exception:
            pass

    def get_frame(self):
        with self._lock:
            return None if self._frame is None else self._frame.copy()

    def set_speed(self, speed):
        with self._lock:
            self.sim.set_target_speed(speed)

    # ---------- 指标 ----------
    def center_error(self):
        with self._lock:
            best = None
            for tg in self.sim.snapshot()["targets"]:
                if not tg.get("alive", True):
                    continue
                d = math.hypot(tg["x"] - self.width / 2.0, tg["y"] - self.height / 2.0)
                if best is None or d < best:
                    best = d
            return 999.0 if best is None else float(best)

    def samples(self):
        with self._lock:
            return list(self._samples)

    # ---------- 生命周期 ----------
    def _render(self):
        frame = np.full((self.height, self.width, 3), 26, dtype=np.uint8)
        for i in range(0, self.width, 40):
            cv2.line(frame, (i, 0), (i, self.height), (38, 38, 38), 1)
            cv2.line(frame, (0, i), (self.width, i), (38, 38, 38), 1)
        snap = self.sim.snapshot()
        for tg in snap["targets"]:
            if tg.get("alive", True):
                draw_ball(frame, tg["x"], tg["y"], max(tg["w"], tg["h"]) / 2.0)
        cv2.drawMarker(frame, (self.width // 2, self.height // 2), (0, 0, 255),
                       cv2.MARKER_CROSS, 16, 1)
        return frame

    def _loop(self):
        last = time.time()
        writer = None
        if self.out_dir:
            os.makedirs(self.out_dir, exist_ok=True)
            writer = cv2.VideoWriter(os.path.join(self.out_dir, "virtual_range.avi"),
                                     cv2.VideoWriter_fourcc(*"MJPG"), 60, (self.width, self.height))
        t0 = time.time()
        frame_idx = 0
        frames_dir = os.path.join(self.out_dir, "frames") if self.out_dir else None
        if frames_dir:
            os.makedirs(frames_dir, exist_ok=True)
        while self._running:
            now = time.time()
            dt = now - last
            last = now
            with self._lock:
                self.sim.step(dt)
                frame = self._render()
                self._frame = frame
                if self.record:
                    self._samples.append((round(now - t0, 4),
                                          [(t["id"], t["x"], t["y"]) for t in self.sim.snapshot()["targets"]]))
                    self._samples = self._samples[-20000:]
            if frames_dir and frame_idx % 90 == 0:
                try:
                    cv2.imwrite(os.path.join(frames_dir, f"vf{frame_idx:05d}.png"), frame)
                except Exception:
                    pass
            frame_idx += 1
            if writer is not None:
                writer.write(frame)
            sleep = 1.0 / 120.0 - (time.time() - now)
            if sleep > 0:
                time.sleep(sleep)
        if writer is not None:
            writer.release()

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2)
