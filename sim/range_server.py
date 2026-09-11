"""合成靶场本地服务：托管靶场页面 + 双向 WebSocket + 真值/命中日志。

- 浏览器只负责把服务器下发的目标画出来，并上报光标/点击/控制指令。
- 主程序通过 POST /overlay 把检测框、预测点等叠加信息推给页面。
- 真值（服务器权威）与命中都落盘，供 analyze.py 离线比对。
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime

from aiohttp import web, WSMsgType

from .motion import Simulation

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


class RangeState:
    def __init__(self, sim: Simulation, out_dir: str, tick_hz: float = 120.0, log_hz: float = 60.0, sens: float = 1.0):
        self.sim = sim
        self.out_dir = out_dir
        self.tick_dt = 1.0 / max(1.0, float(tick_hz))
        self.log_dt = 1.0 / max(1.0, float(log_hz))
        self.sens = float(sens)
        self.task = None
        self.clients: set[web.WebSocketResponse] = set()
        self.latest_overlay = None
        self._truth_fp = None
        self._event_fp = None
        self._overlay_fp = None
        self._last_log = 0.0
        self._frame = 0
        self.t0 = time.time()

    def open_logs(self):
        os.makedirs(self.out_dir, exist_ok=True)
        self._truth_fp = open(os.path.join(self.out_dir, "truth.jsonl"), "a", encoding="utf-8", buffering=1)
        self._event_fp = open(os.path.join(self.out_dir, "events.jsonl"), "a", encoding="utf-8", buffering=1)
        self._overlay_fp = open(os.path.join(self.out_dir, "overlay.jsonl"), "a", encoding="utf-8", buffering=1)
        with open(os.path.join(self.out_dir, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(
                {
                    "started": datetime.now().isoformat(timespec="seconds"),
                    "width": self.sim.width,
                    "height": self.sim.height,
                    "mode": self.sim.mode,
                    "count": self.sim.count,
                    "class_ids": self.sim.class_ids,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

    def close_logs(self):
        for fp in (self._truth_fp, self._event_fp, self._overlay_fp):
            try:
                if fp:
                    fp.flush()
                    fp.close()
            except Exception:
                pass

    def log_truth(self, snap: dict, now: float):
        if self._truth_fp is None:
            return
        rec = {"t": round(now, 4), "frame": snap["frame"], "targets": snap["targets"]}
        self._truth_fp.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def log_event(self, event: dict, now: float):
        if self._event_fp is None:
            return
        rec = {"t": round(now, 4), **event}
        self._event_fp.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self._event_fp.flush()

    def log_overlay(self, overlay: dict, now: float):
        if self._overlay_fp is None:
            return
        self._overlay_fp.write(json.dumps({"t": round(now, 4), **overlay}, ensure_ascii=False) + "\n")


async def _broadcast(state: RangeState, message: dict):
    if not state.clients:
        return
    payload = json.dumps(message, ensure_ascii=False)
    dead = []
    for ws in list(state.clients):
        try:
            await ws.send_str(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        state.clients.discard(ws)


async def _sim_loop(app: web.Application):
    state: RangeState = app["state"]
    await _broadcast(state, {"type": "config", "config": _config(state)})
    loop = asyncio.get_event_loop()
    last = loop.time()
    while True:
        await asyncio.sleep(state.tick_dt)
        now_mono = loop.time()
        dt = now_mono - last
        last = now_mono
        snap = state.sim.step(dt)
        state._frame = snap["frame"]
        now = time.time() - state.t0
        await _broadcast(state, {"type": "frame", "t": round(now, 4), **snap})
        if now - state._last_log >= state.log_dt:
            state._last_log = now
            state.log_truth(snap, now)


async def _start_sim(app: web.Application):
    state: RangeState = app["state"]
    state.open_logs()
    state.task = asyncio.create_task(_sim_loop(app))


async def _stop_sim(app: web.Application):
    state: RangeState = app["state"]
    task = getattr(state, "task", None)
    if task is not None:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    state.close_logs()


def _config(state: RangeState) -> dict:
    sim = state.sim
    return {
        "width": sim.width,
        "height": sim.height,
        "center": [sim.width / 2, sim.height / 2],
        "sens": state.sens,
        "mode": sim.mode,
        "count": sim.count,
        "class_ids": sim.class_ids,
        "min_speed": sim.min_speed,
        "max_speed": sim.max_speed,
    }


async def _index(request: web.Request):
    return web.FileResponse(os.path.join(STATIC_DIR, "index.html"))


async def _health(request: web.Request):
    state: RangeState = request.app["state"]
    return web.json_response({"ok": True, "clients": len(state.clients), "frame": state._frame})


async def _overlay(request: web.Request):
    state: RangeState = request.app["state"]
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid json"}, status=400)
    state.latest_overlay = data
    state.log_overlay(data, time.time() - state.t0)
    await _broadcast(state, {"type": "overlay", "data": data})
    return web.json_response({"ok": True})


async def _ws(request: web.Request):
    state: RangeState = request.app["state"]
    ws = web.WebSocketResponse(max_msg_size=2 * 1024 * 1024)
    await ws.prepare(request)
    state.clients.add(ws)
    await ws.send_json({"type": "config", "config": _config(state)})
    if state.latest_overlay is not None:
        await ws.send_json({"type": "overlay", "data": state.latest_overlay})
    try:
        async for msg in ws:
            if msg.type != WSMsgType.TEXT:
                continue
            try:
                data = json.loads(msg.data)
            except Exception:
                continue
            mtype = data.get("type")
            now = time.time() - state.t0
            if mtype == "mouse_delta":
                try:
                    state.sim.pan(float(data.get("dx", 0.0)), float(data.get("dy", 0.0)), state.sens)
                except Exception:
                    pass
            elif mtype == "click":
                target = state.sim.center_hit()
                event = {
                    "kind": "click",
                    "cursor_x": data.get("x"),
                    "cursor_y": data.get("y"),
                    "button": data.get("button"),
                    "hit": target is not None,
                    "target_id": target.tid if target else None,
                    "client_t": data.get("t"),
                }
                state.log_event(event, now)
                await _broadcast(state, {"type": "hit", "t": round(now, 4), **event})
            elif mtype == "cursor":
                pass
            elif mtype == "hello":
                state.log_event({"kind": "hello", **data}, now)
            elif mtype == "control":
                _apply_control(state, data)
                await _broadcast(state, {"type": "config", "config": _config(state)})
    finally:
        state.clients.discard(ws)
    return ws


def _apply_control(state: RangeState, data: dict):
    sim = state.sim
    if data.get("mode") in Simulation.MODES:
        sim.set_mode(data["mode"])
    if "count" in data:
        try:
            sim.set_count(int(data["count"]))
        except Exception:
            pass
    if "min_speed" in data or "max_speed" in data:
        try:
            sim.set_speed(
                float(data.get("min_speed", sim.min_speed)),
                float(data.get("max_speed", sim.max_speed)),
            )
        except Exception:
            pass
    if "sens" in data:
        try:
            state.sens = max(0.05, float(data["sens"]))
        except Exception:
            pass


def create_app(out_dir: str, width: int = 320, height: int = 320, mode: str = "bounce",
               count: int = 1, class_ids=None, tick_hz: float = 120.0, log_hz: float = 60.0,
               seed=None, sens: float = 1.0, min_speed: float = 120.0,
               max_speed: float = 320.0) -> web.Application:
    sim = Simulation(width=width, height=height, mode=mode, count=count, class_ids=class_ids,
                     seed=seed, min_speed=min_speed, max_speed=max_speed)
    state = RangeState(sim, out_dir, tick_hz=tick_hz, log_hz=log_hz, sens=sens)
    app = web.Application()
    app["state"] = state
    app.router.add_get("/", _index)
    app.router.add_get("/health", _health)
    app.router.add_post("/overlay", _overlay)
    app.router.add_get("/ws", _ws)
    if os.path.isdir(STATIC_DIR):
        app.router.add_static("/static/", STATIC_DIR)
    app.on_startup.append(_start_sim)
    app.on_cleanup.append(_stop_sim)
    return app


def main():
    import argparse

    parser = argparse.ArgumentParser(description="DOPA 合成靶场服务")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--size", type=int, default=320)
    parser.add_argument("--width", type=int, default=None)
    parser.add_argument("--height", type=int, default=None)
    parser.add_argument("--mode", default="bounce", choices=list(Simulation.MODES))
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--classes", default="32", help="逗号分隔的类别 id")
    parser.add_argument("--tick-hz", type=float, default=120.0)
    parser.add_argument("--log-hz", type=float, default=60.0)
    parser.add_argument("--out", default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--sens", type=float, default=1.0, help="鼠标计数 -> 屏幕像素")
    parser.add_argument("--min-speed", type=float, default=120.0)
    parser.add_argument("--max-speed", type=float, default=320.0)
    args = parser.parse_args()

    width = args.width or args.size
    height = args.height or args.size
    class_ids = [int(x) for x in str(args.classes).split(",") if x.strip() != ""]
    out_dir = args.out or os.path.join("logs", "range", datetime.now().strftime("%Y%m%d_%H%M%S"))
    app = create_app(
        out_dir=out_dir,
        width=width,
        height=height,
        mode=args.mode,
        count=args.count,
        class_ids=class_ids or None,
        tick_hz=args.tick_hz,
        log_hz=args.log_hz,
        seed=args.seed,
        sens=args.sens,
        min_speed=args.min_speed,
        max_speed=args.max_speed,
    )
    print(f"[靶场] http://{args.host}:{args.port}/  日志: {out_dir}")
    web.run_app(app, host=args.host, port=args.port, print=None)


if __name__ == "__main__":
    main()
