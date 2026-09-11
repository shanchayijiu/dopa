"""移动靶速度扫描：注入专用靶场组，跑原生 app，逐级提速测追踪。

目的：验证"移动靶追踪"（ByteTrack 速度 + Kalman 前馈）在不同速度下的锁定效果，
而不是只看静止目标。PID 只负责收敛，移动靶靠前馈 lead。

用法:
  python tools/track_speed_sweep.py --speeds 150,300,450,600,750,900 --duration 1.6
  python tools/track_speed_sweep.py --predict-gain 1.0 --predict-frames 8 --lead-smooth 0.4
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

MODEL = os.path.join("models", "yolov8n_320.onnx")


def make_range_group(classes, kp, ki, kd, integral_limit):
    key = {
        "classes": list(classes),
        "pid_kp_x": kp, "pid_kp_y": kp,
        "pid_ki_x": ki, "pid_ki_y": ki,
        "pid_kd_x": kd, "pid_kd_y": kd,
        "pid_integral_limit_x": integral_limit, "pid_integral_limit_y": integral_limit,
        "smooth_x": 0.0, "smooth_y": 0.0, "smooth_deadzone": 0.0,
        "move_deadzone": 0.0,
        "min_position_offset": 0.0,
        "aim_bot_position": 0.5, "aim_bot_position2": 0.5,
        "tracker_enabled": True,
        "trigger": {"status": False},
    }
    return {
        "infer_model": MODEL,
        "original_infer_model": MODEL,
        "is_v8": True, "is_trt": False, "model_variant": "onnx",
        "aim_keys": {"mouse_left": key},
    }


def _med(v):
    if not v:
        return None
    s = sorted(v)
    k = len(s) // 2
    return round(s[k] if len(s) % 2 else (s[k - 1] + s[k]) / 2, 2)


def _p95(v):
    if not v:
        return None
    s = sorted(v)
    return round(s[max(0, min(len(s) - 1, int(round(0.95 * (len(s) - 1)))))], 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--speeds", default="150,300,450,600,750,900")
    ap.add_argument("--settle", type=float, default=1.2)
    ap.add_argument("--duration", type=float, default=1.6, help="每个速度的采样时长")
    ap.add_argument("--classes", default="32,29")
    ap.add_argument("--kp", type=float, default=0.2)
    ap.add_argument("--ki", type=float, default=0.0)
    ap.add_argument("--kd", type=float, default=0.001)
    ap.add_argument("--integral-limit", type=float, default=8.0)
    ap.add_argument("--predict-gain", type=float, default=3.0)
    ap.add_argument("--predict-frames", type=int, default=5)
    ap.add_argument("--min-lead-speed", type=float, default=60.0)
    ap.add_argument("--max-lead", type=float, default=40.0)
    ap.add_argument("--lead-smooth", type=float, default=0.18)
    ap.add_argument("--process-noise", type=float, default=0.5)
    ap.add_argument("--measurement-noise", type=float, default=15.0)
    ap.add_argument("--no-kalman", action="store_true")
    ap.add_argument("--no-curve", action="store_true", help="关闭曲线移动（原生默认开启）")
    ap.add_argument("--out", default=os.path.join("logs", "speed_sweep"))
    ap.add_argument("--window", action="store_true")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    classes = [int(x) for x in args.classes.split(",") if x.strip()]
    speeds = [float(x) for x in args.speeds.split(",") if x.strip()]

    from sim.virtual_game import VirtualGame, set_shared_game, ensure_window

    game = VirtualGame(mode="bounce", count=1, class_ids=tuple(classes),
                       show=bool(args.window), out_dir=(args.out if args.window else None))
    game.sim.set_target_speed(speeds[0])
    set_shared_game(game)
    game.start()

    import cv2
    if args.window:
        ensure_window("speed sweep")
    val = None
    try:
        from core import Valorant
        val = Valorant()
        cfg = val.config
        cfg['groups']['range'] = make_range_group(classes, args.kp, args.ki, args.kd,
                                                  args.integral_limit)
        cfg['group'] = 'range'
        val.group = 'range'
        val.aim_keys_dist = cfg['groups']['range']['aim_keys']
        val.aim_key = ['mouse_left']
        val.select_key = 'mouse_left'
        val.old_pressed_aim_key = 'mouse_left'
        val.pressed_key_config = val.aim_keys_dist['mouse_left']

        cfg['virtual_test'] = True
        cfg['single_machine_mode'] = False
        cfg['infer_debug'] = False
        cfg['print_fps'] = False
        cfg['inference_device'] = 'DML'
        if args.no_curve:
            cfg['is_curve'] = False
            cfg['is_curve_uniform'] = False
        cfg['target_id_lock_enabled'] = True
        cfg['kalman'] = {
            'enabled': not args.no_kalman,
            'predict_frames': args.predict_frames,
            'predict_gain': args.predict_gain,
            'process_noise': args.process_noise,
            'measurement_noise': args.measurement_noise,
        }
        val.refresh_controller_params()

        val.refresh_engine()
        if val.engine is None:
            print('[sweep] 引擎未加载')
            return 3
        ap_ = val.aim_pipeline
        ap_.kalman_enabled = not args.no_kalman
        ap_.predict_gain = args.predict_gain
        ap_.kalman_predict_frames = args.predict_frames
        ap_.min_lead_speed = args.min_lead_speed
        ap_.max_lead = args.max_lead
        ap_._lead_smooth = args.lead_smooth

        val.running = True
        val.end = False
        if not val.go():
            print('[sweep] go() 失败')
            return 4
        val.aim_key_status = True

        rows = []
        for v in speeds:
            game.set_speed(v)
            if args.window:
                end = time.time() + args.settle
                while time.time() < end:
                    fr = game.get_frame()
                    if fr is not None:
                        cv2.imshow("speed sweep", fr)
                        cv2.waitKey(1)
                    time.sleep(0.01)
            else:
                time.sleep(args.settle)
            errs, app_errs = [], []
            t_end = time.time() + args.duration
            while time.time() < t_end:
                errs.append(game.center_error())
                pos = getattr(val.aim_pipeline, '_last_output_target_pos', None)
                if pos is not None:
                    app_errs.append(math.hypot(pos[0] - val.screen_center_x,
                                               pos[1] - val.screen_center_y))
                if args.window:
                    fr = game.get_frame()
                    if fr is not None:
                        cv2.imshow("speed sweep", fr)
                        cv2.waitKey(1)
                time.sleep(0.005)
            in20 = sum(1 for e in errs if e <= 20.0) / max(1, len(errs))
            rows.append({
                "speed": v, "n": len(errs),
                "game_err_med": _med(errs), "game_err_p95": _p95(errs),
                "app_err_med": _med(app_errs),
                "frac_in_20": round(in20, 2),
            })
            print(f"[sweep] v={v:6.0f}  ball_err_med={rows[-1]['game_err_med']!s:>6} "
                  f"p95={rows[-1]['game_err_p95']!s:>6} app_err_med={rows[-1]['app_err_med']!s:>6} "
                  f"in20={rows[-1]['frac_in_20']}")

        meta = {
            "model": MODEL, "kalman": not args.no_kalman,
            "kp": args.kp, "ki": args.ki, "kd": args.kd,
            "predict_gain": args.predict_gain, "predict_frames": args.predict_frames,
            "min_lead_speed": args.min_lead_speed, "max_lead": args.max_lead,
            "lead_smooth": args.lead_smooth,
            "process_noise": args.process_noise, "measurement_noise": args.measurement_noise,
            "infer_fps": getattr(val, 'fps', None),
        }
        out = {"meta": meta, "rows": rows}
        tag = "on" if not args.no_kalman else "off"
        path = os.path.join(args.out, f"sweep_{tag}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"[sweep] 写入 {path}")
        return 0
    finally:
        try:
            if val is not None:
                val.running = False
                if getattr(val, 'timer_id', 0):
                    val.time_kill_event(val.timer_id)
                    val.timer_id = 0
                val.close_screenshot()
                val._secure_cleanup()
        except Exception:
            pass
        game.stop()
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
