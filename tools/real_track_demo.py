"""真实模型闭环演示：真 ONNX 推理 + 真 NMS + 真 AimPipeline，跑移动球并出效果。

与单元/回放不同，这里用的是 models/yolov8n_320.onnx 真推理，逐帧渲染一个球、
过项目真实后处理(nms_v8)，再喂进真实 AimPipeline，闭环把 PID 输出当作相机平移。
会输出带标注的 PNG 关键帧、AVI 视频和指标，便于肉眼确认锁定效果。

用法:
  python tools/real_track_demo.py --speed 350 --duration 4
  python tools/real_track_demo.py --speed 350 --save-frames
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from aim.aim_pipeline import AimPipeline  # noqa: E402
from inference.infer_function import nms_v8, read_img  # noqa: E402
from sim.metrics import lock_metrics  # noqa: E402
from sim.replay import DEFAULT_KEY, configure_pipeline, default_cfg  # noqa: E402

PF = 320


def _providers():
    import onnxruntime as ort

    avail = ort.get_available_providers()
    if "DmlExecutionProvider" in avail:
        return ["DmlExecutionProvider", "CPUExecutionProvider"]
    return ["CPUExecutionProvider"]


def _draw_ball(frame, x, y, r=24):
    cv2.circle(frame, (int(x), int(y)), int(r), (60, 200, 120), -1)
    cv2.circle(frame, (int(x), int(y)), int(r), (20, 120, 60), 3)
    cv2.ellipse(frame, (int(x), int(y)), (int(r), int(r)), 0, 30, 150, (255, 255, 255), 4)
    cv2.ellipse(frame, (int(x), int(y)), (int(r), int(r)), 0, 210, 330, (255, 255, 255), 4)


def _bg():
    f = np.full((PF, PF, 3), 26, dtype=np.uint8)
    for i in range(0, PF, 40):
        cv2.line(f, (i, 0), (i, PF), (38, 38, 38), 1)
        cv2.line(f, (0, i), (PF, i), (38, 38, 38), 1)
    return f


def run(speed, duration, out_dir, classes=(32, 29), conf=0.4, iou=0.5,
        use_kalman=True, save_frames=False, fps=100.0):
    import onnxruntime as ort

    os.makedirs(out_dir, exist_ok=True)
    model = os.path.join(ROOT, "models", "yolov8n_320.onnx")
    providers = _providers()
    sess = ort.InferenceSession(model, providers=providers)
    iname = sess.get_inputs()[0].name
    print(f"[demo] model={model}")
    print(f"[demo] providers={providers}")

    pipeline = AimPipeline()
    configure_pipeline(pipeline, DEFAULT_KEY)
    pipeline.kalman_enabled = use_kalman
    cfg = default_cfg(use_kalman, small_target_enhancement={
        "enabled": False, "smooth_enabled": False, "adaptive_nms": False})

    center = (PF / 2.0, PF / 2.0)
    dt = 1.0 / fps
    world = [100.0, 160.0]
    cam = [0.0, 0.0]
    errors = []
    id_switches = 0
    prev_id = None
    det_frames = 0
    bg = _bg()

    frames_dir = os.path.join(out_dir, "frames")
    if save_frames:
        os.makedirs(frames_dir, exist_ok=True)
    writer = cv2.VideoWriter(os.path.join(out_dir, "demo.avi"),
                             cv2.VideoWriter_fourcc(*"MJPG"), 20, (PF, PF))

    total = int(duration * fps)
    snap_at = {0, 10, 20, 40, int(0.5 * total), total - 1}
    for i in range(total):
        world[0] += speed * dt
        sx = world[0] - cam[0]
        sy = world[1] - cam[1]

        frame = bg.copy()
        _draw_ball(frame, sx, sy)
        blob = read_img(frame, (PF, PF))
        pred = sess.run(None, {iname: blob})[0]
        boxes, scores, cls = nms_v8(pred, conf, iou, adaptive_nms=False)
        boxes = np.asarray(boxes, dtype=np.float32).reshape(-1, 4)
        cls = np.asarray(cls, dtype=np.int64).reshape(-1)

        sel = np.isin(cls, np.asarray(classes, dtype=np.int64))
        boxes_f = boxes[sel]
        cls_f = cls[sel]
        if len(boxes_f):
            det_frames += 1

        payload = {
            "frame_id": i,
            "boxes": boxes_f,
            "class_ids": cls_f.tolist(),
            "input_w": float(PF),
            "input_h": float(PF),
        }
        out = pipeline.step_frame(payload, DEFAULT_KEY, cfg, center, 0.0, 0.0, 0.0, float(PF * PF))

        err = math.hypot(sx - center[0], sy - center[1])
        errors.append(err)
        if out:
            cam[0] += out[0]
            cam[1] += out[1]
        tid = getattr(pipeline, "_last_output_target_id", None)
        if tid is not None and prev_id is not None and tid != prev_id:
            id_switches += 1
        if tid is not None:
            prev_id = tid

        ann = frame.copy()
        for b in boxes_f:
            cx, cy, w, h = b
            cv2.rectangle(ann, (int(cx - w / 2), int(cy - h / 2)),
                          (int(cx + w / 2), int(cy + h / 2)), (0, 220, 140), 1)
        cross = (int(center[0]), int(center[1]))
        cv2.drawMarker(ann, cross, (0, 0, 255), cv2.MARKER_CROSS, 16, 1)
        cv2.putText(ann, f"v={speed:.0f}px/s err={err:5.1f} id={tid} det={len(boxes_f)}",
                    (6, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (230, 230, 230), 1)
        cv2.putText(ann, f"out={out} lead=({pipeline._lead_x:.1f},{pipeline._lead_y:.1f})",
                    (6, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180, 200, 255), 1)
        cv2.putText(ann, "[kalman ON]" if use_kalman else "[kalman OFF]",
                    (6, 44), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 255, 255) if use_kalman else (120, 120, 120), 1)
        writer.write(ann)
        if save_frames and i in snap_at:
            cv2.imwrite(os.path.join(frames_dir, f"f{i:04d}.png"), ann)

    writer.release()
    m = lock_metrics(errors, fps)
    result = {
        "speed": speed, "use_kalman": use_kalman, "fps": fps, "frames": total,
        "detection_rate": round(det_frames / max(1, total), 4),
        "id_switches": id_switches, **m,
    }
    with open(os.path.join(out_dir, "result.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("[demo] result:", json.dumps(result, ensure_ascii=False))
    print(f"[demo] 视频: {os.path.join(out_dir, 'demo.avi')}")
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--speed", type=float, default=350.0)
    ap.add_argument("--duration", type=float, default=4.0)
    ap.add_argument("--out", default=os.path.join("logs", "real_track"))
    ap.add_argument("--classes", default="32,29")
    ap.add_argument("--no-kalman", action="store_true")
    ap.add_argument("--save-frames", action="store_true")
    args = ap.parse_args()
    classes = tuple(int(x) for x in args.classes.split(",") if x.strip())
    run(args.speed, args.duration, args.out, classes=classes,
        use_kalman=not args.no_kalman, save_frames=args.save_frames)


if __name__ == "__main__":
    main()
