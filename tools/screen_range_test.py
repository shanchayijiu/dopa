"""真实屏幕靶场测试：BetterCam 抓屏 + 真模型 + 真 AimPipeline + 本机鼠标移动。

流程：起靶场服务 → 全屏打开靶场页面 → 点一下锁定鼠标 → 循环
  BetterCam 抓屏幕中心 → 真推理/nms_v8 → AimPipeline → pydirectinput 移动
页面按鼠标增量平移视角，形成真实闭环。输出带标注的关键帧、指标和 result.json。

用法:
  python tools/screen_range_test.py --duration 10 --speed 320
  python tools/screen_range_test.py --duration 10 --no-lock   # 不点击锁定(用光标增量回退)
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sim.launch_range import find_browser  # noqa: E402
from sim.overlay_client import healthy, post_overlay  # noqa: E402
from sim.metrics import lock_metrics  # noqa: E402
from sim.replay import DEFAULT_KEY, configure_pipeline, default_cfg  # noqa: E402

SIZE = 320


def focus_window(timeout=10.0):
    """把标题含“靶场/DOPA”的浏览器窗口置顶最大化。"""
    import win32gui
    import win32con

    found = {"ok": False}

    def cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return True
        title = win32gui.GetWindowText(hwnd)
        if "靶场" in title or "DOPA" in title:
            try:
                win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
                win32gui.SetForegroundWindow(hwnd)
                found["ok"] = True
                found["title"] = title
                return False
            except Exception:
                return True
        return True

    end = time.time() + timeout
    while time.time() < end and not found["ok"]:
        win32gui.EnumWindows(cb, None)
        if not found["ok"]:
            time.sleep(0.3)
    return found["ok"]


def _providers():
    import onnxruntime as ort

    avail = ort.get_available_providers()
    return ["DmlExecutionProvider", "CPUExecutionProvider"] if "DmlExecutionProvider" in avail \
        else ["CPUExecutionProvider"]


def _wait(fn, timeout=15.0, interval=0.2):
    end = time.time() + timeout
    while time.time() < end:
        try:
            if fn():
                return True
        except Exception:
            pass
        time.sleep(interval)
    return False


def main():
    import win32api
    import pydirectinput
    import bettercam
    from aim.aim_pipeline import AimPipeline
    from inference.infer_function import nms_v8, read_img
    import onnxruntime as ort

    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=float, default=10.0)
    ap.add_argument("--fps", type=float, default=100.0)
    ap.add_argument("--port", type=int, default=8899)
    ap.add_argument("--speed", type=float, default=320.0)
    ap.add_argument("--classes", default="32,29")
    ap.add_argument("--out", default=os.path.join("logs", "screen_range"))
    ap.add_argument("--no-lock", action="store_true")
    ap.add_argument("--no-kalman", action="store_true")
    args = ap.parse_args()

    classes = tuple(int(x) for x in args.classes.split(",") if x.strip())
    classes_arr = np.asarray(classes, dtype=np.int64)
    os.makedirs(args.out, exist_ok=True)

    sw, sh = win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1)
    region = ((sw - SIZE) // 2, (sh - SIZE) // 2, (sw - SIZE) // 2 + SIZE, (sh - SIZE) // 2 + SIZE)
    print(f"[screen] 屏幕 {sw}x{sh}, 抓取区域 {region}")

    server = subprocess.Popen(
        [sys.executable, "-m", "sim.range_server", "--size", str(SIZE), "--port", str(args.port),
         "--mode", "bounce", "--count", "1", "--min-speed", str(max(60, args.speed * 0.8)),
         "--max-speed", str(args.speed)],
        cwd=ROOT,
    )
    browser_proc = None
    cam = None
    pydirectinput.PAUSE = 0
    pydirectinput.FAILSAFE = False
    try:
        if not _wait(lambda: healthy(args.port)):
            print("[screen] 靶场服务未就绪")
            return 1

        browser = find_browser(None)
        if not browser:
            print("[screen] 未找到浏览器")
            return 1
        udd = os.path.join(os.environ.get("TEMP", "."), f"dopa_screen_range_{args.port}")
        url = f"http://127.0.0.1:{args.port}/?size={SIZE}"
        browser_proc = subprocess.Popen(
            [browser, f"--app={url}", "--start-fullscreen", f"--user-data-dir={udd}",
             "--no-first-run", "--no-default-browser-check"],
            cwd=ROOT,
        )
        print("[screen] 等待页面加载并置顶...")
        time.sleep(3.0)
        if focus_window(browser_proc.pid):
            print("[screen] 已置顶靶场窗口")
        else:
            print("[screen] 未找到靶场窗口标题，继续尝试")
            time.sleep(3.0)
        time.sleep(1.0)

        if not args.no_lock:
            pydirectinput.moveTo(sw // 2, sh // 2)
            time.sleep(0.2)
            pydirectinput.click()
            time.sleep(0.5)

        cam = bettercam.create(output_color="BGR", max_buffer_len=4, region=region)
        cam.start(target_fps=0, video_mode=True)
        time.sleep(0.5)

        sess = ort.InferenceSession(os.path.join(ROOT, "models", "yolov8n_320.onnx"),
                                    providers=_providers())
        iname = sess.get_inputs()[0].name

        pipeline = AimPipeline()
        configure_pipeline(pipeline, DEFAULT_KEY)
        pipeline.kalman_enabled = not args.no_kalman
        cfg = default_cfg(not args.no_kalman,
                          small_target_enhancement={"enabled": False, "smooth_enabled": False,
                                                    "adaptive_nms": False})
        center = (SIZE / 2.0, SIZE / 2.0)

        errors, det_frames, id_switches = [], 0, 0
        prev_id = None
        frames_dir = os.path.join(args.out, "frames")
        os.makedirs(frames_dir, exist_ok=True)
        writer = cv2.VideoWriter(os.path.join(args.out, "screen.avi"),
                                 cv2.VideoWriter_fourcc(*"MJPG"), 20, (SIZE, SIZE))
        dt = 1.0 / args.fps
        t_end = time.time() + args.duration
        i = 0
        t0 = time.time()
        snap_at = {0, 30, 90, int(args.fps * 3), int(args.fps * 6)}
        while time.time() < t_end:
            loop_start = time.perf_counter()
            frame = cam.get_latest_frame()
            if frame is None:
                time.sleep(0.005)
                continue
            frame = frame.copy()
            pred = sess.run(None, {iname: read_img(frame, (SIZE, SIZE))})[0]
            boxes, scores, cls = nms_v8(pred, 0.25, 0.5, adaptive_nms=False)
            boxes = np.asarray(boxes, dtype=np.float32).reshape(-1, 4)
            cls = np.asarray(cls, dtype=np.int64).reshape(-1)
            sel = np.isin(cls, classes_arr)
            boxes_f, cls_f = boxes[sel], cls[sel]
            if len(boxes_f):
                det_frames += 1

            payload = {"frame_id": i, "boxes": boxes_f, "class_ids": cls_f.tolist(),
                       "input_w": float(SIZE), "input_h": float(SIZE)}
            out = pipeline.step_frame(payload, DEFAULT_KEY, cfg, center, 0.0, 0.0, 0.0, float(SIZE * SIZE))

            # 观测误差：离屏幕中心最近的检测框
            if len(boxes_f):
                d2 = ((boxes_f[:, 0] - center[0]) ** 2 + (boxes_f[:, 1] - center[1]) ** 2)
                k = int(np.argmin(d2))
                errors.append(float(np.sqrt(d2[k])))
            else:
                errors.append(errors[-1] if errors else 999.0)

            if out:
                pydirectinput.moveRel(int(out[0]), int(out[1]))
            tid = getattr(pipeline, "_last_output_target_id", None)
            if tid is not None and prev_id is not None and tid != prev_id:
                id_switches += 1
            if tid is not None:
                prev_id = tid

            # 注意：不能在抓屏循环里把检测框画回页面，否则会污染下一帧的检测。
            # 如需在页面看框，请另开一个不参与抓取的显示端。

            ann = frame.copy()
            for b in boxes_f:
                cx, cy, w, h = b
                cv2.rectangle(ann, (int(cx - w / 2), int(cy - h / 2)),
                              (int(cx + w / 2), int(cy + h / 2)), (0, 220, 140), 1)
            cv2.drawMarker(ann, (int(center[0]), int(center[1])), (0, 0, 255),
                           cv2.MARKER_CROSS, 16, 1)
            err_now = errors[-1]
            cv2.putText(ann, f"err={err_now:5.1f} id={tid} det={len(boxes_f)} out={out}",
                        (6, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (230, 230, 230), 1)
            cv2.putText(ann, "[REAL SCREEN][kalman ON]" if not args.no_kalman else "[REAL SCREEN][kalman OFF]",
                        (6, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 255, 255), 1)
            writer.write(ann)
            if i in snap_at:
                cv2.imwrite(os.path.join(frames_dir, f"f{i:04d}.png"), ann)
                cv2.imwrite(os.path.join(frames_dir, f"raw_{i:04d}.png"), frame)

            i += 1
            spent = time.perf_counter() - loop_start
            if spent < dt:
                time.sleep(dt - spent)

        writer.release()
        elapsed = time.time() - t0
        m = lock_metrics(errors, args.fps)
        result = {
            "mode": "screen", "duration": round(elapsed, 2), "frames": i,
            "measured_fps": round(i / max(1e-6, elapsed), 1),
            "detection_rate": round(det_frames / max(1, i), 4),
            "id_switches": id_switches, "kalman": not args.no_kalman, **m,
        }
        with open(os.path.join(args.out, "result.json"), "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print("[screen] result:", json.dumps(result, ensure_ascii=False))
        print(f"[screen] 视频 {os.path.join(args.out, 'screen.avi')} 关键帧 {frames_dir}")
        return 0
    finally:
        if cam is not None:
            try:
                cam.stop()
            except Exception:
                pass
        if browser_proc is not None:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(browser_proc.pid)],
                           capture_output=True)
        server.terminate()
        try:
            server.wait(timeout=5)
        except Exception:
            server.kill()


if __name__ == "__main__":
    sys.exit(main())
