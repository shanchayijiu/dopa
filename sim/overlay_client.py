"""主程序 -> 靶场服务 的叠加信息推送（纯标准库，避免给主程序加依赖）。"""
from __future__ import annotations

import json
import threading
import time
import urllib.request


def post_overlay(port: int, payload: dict, host: str = "127.0.0.1", timeout: float = 0.15) -> bool:
    url = f"http://{host}:{port}/overlay"
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def healthy(port: int, host: str = "127.0.0.1", timeout: float = 0.5) -> bool:
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/health", timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


class OverlayPusher:
    """后台线程按固定频率把最新 overlay 推给靶场，不阻塞推理主循环。"""

    def __init__(self, port: int, host: str = "127.0.0.1", hz: float = 30.0):
        self.port = int(port)
        self.host = host
        self.interval = 1.0 / max(1.0, float(hz))
        self._payload = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def push(self, payload: dict):
        with self._lock:
            self._payload = payload

    def _loop(self):
        while not self._stop.is_set():
            payload = None
            with self._lock:
                payload, self._payload = self._payload, None
            if payload is not None:
                post_overlay(self.port, payload, self.host)
            time.sleep(self.interval)

    def stop(self):
        self._stop.set()

