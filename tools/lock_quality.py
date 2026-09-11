"""锁定质量测量：固定速度，量化误差抖动（std / 振荡频率 / 10px 内占比）。

用途：区分"牢牢锁定"与"准星附近抽搐"。
用法:
  python tools/lock_quality.py --motion orbit --speed 250 --duration 10
  python tools/lock_quality.py --no-kalman
  python tools/lock_quality.py --lead-smooth 0.5 --predict-gain 1.0
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--motion", default="orbit")
    ap.add_argument("--speed", type=float, default=250.0)
    ap.add_argument("--duration", type=float, default=10.0)
    ap.add_argument("--classes", default="32,29")
    ap.add_argument("--kp", type=float, default=0.35)
    ap.add_argument("--ki", type=float, default=1.0)
    ap.add_argument("--kd", type=float, default=0.001)
    ap.add_argument("--predict-gain", dest="predict_gain", type=float, default=1.0)
    ap.add_argument("--predict-frames", dest="predict_frames", type=int, default=5)
    ap.add_argument("--min-lead-speed", dest="min_lead_speed", type=float, default=60.0)
    ap.add_argument("--max-lead", dest="max_lead", type=float, default=40.0)
    ap.add_argument("--lead-smooth", dest="lead_smooth", type=float, default=0.18)
    ap.add_argument("--no-kalman", action="store_true")
    ap.add_argument("--no-curve", action="store_true")
    ap.add_argument("--err-filter", dest="err_filter", type=float, default=0.0)
    ap.add_argument("--vel-filter", dest="vel_filter", type=float, default=0.0)
    ap.add_argument("--window", action="store_true")
    ap.add_argument("--out", default=os.path.join("logs", "lock_quality"))
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    classes = [int(x) for x in args.classes.split(",") if x.strip()]

    from sim.virtual_game import VirtualGame, set_shared_game, ensure_window
    from tools.track_speed_sweep import make_range_group

    game = VirtualGame(mode=args.motion, count=1, class_ids=tuple(classes),
                       show=bool(args.window), out_dir=None)
    game.sim.set_target_speed(args.speed)
    set_shared_game(game)
    game.start()

    import cv2
    if args.window:
        ensure_window("lock quality")
    val = None
    try:
        from core import Valorant
        val = Valorant()
        cfg = val.config
        cfg['groups']['range'] = make_range_group(classes, args.kp, args.ki, args.kd, 8.0)
        gkey = cfg['groups']['range']['aim_keys']['mouse_left']
        gkey['pid_error_filter_alpha'] = float(args.err_filter)
        gkey['pid_vel_filter_alpha'] = float(args.vel_filter)
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
        cfg['target_id_lock_enabled'] = True
        if args.no_curve:
            cfg['is_curve'] = False
            cfg['is_curve_uniform'] = False
        cfg['kalman'] = {
            'enabled': not args.no_kalman, 'predict_frames': args.predict_frames,
            'predict_gain': args.predict_gain, 'process_noise': 0.5, 'measurement_noise': 15.0,
        }
        val.refresh_controller_params()
        val.refresh_engine()
        if val.engine is None:
            print('[lq] 引擎未加载')
            return 3
        a = val.aim_pipeline
        a.kalman_enabled = not args.no_kalman
        a.predict_gain = args.predict_gain
        a.kalman_predict_frames = args.predict_frames
        a.min_lead_speed = args.min_lead_speed
        a.max_lead = args.max_lead
        a._lead_smooth = args.lead_smooth

        val.running = True
        val.end = False
        if not val.go():
            print('[lq] go() 失败')
            return 4
        val.aim_key_status = True

        errs = []
        dt = 0.005
        t_end = time.time() + args.duration
        while time.time() < t_end:
            errs.append(game.center_error())
            if args.window:
                fr = game.get_frame()
                if fr is not None:
                    cv2.imshow("lock quality", fr)
                    cv2.waitKey(1)
            time.sleep(dt)

        n = len(errs)
        mean = sum(errs) / max(1, n)
        var = sum((e - mean) ** 2 for e in errs) / max(1, n)
        std = var ** 0.5
        # 振荡：误差去均值后的过零次数
        zc = 0
        sgn = 0
        for e in errs:
            s = 1 if (e - mean) > 0 else -1
            if sgn != 0 and s != sgn:
                zc += 1
            sgn = s
        in10 = sum(1 for e in errs if e <= 10.0) / max(1, n)
        result = {
            "motion": args.motion, "speed": args.speed, "kalman": not args.no_kalman,
            "curve": not args.no_curve, "lead_smooth": args.lead_smooth,
            "predict_gain": args.predict_gain, "predict_frames": args.predict_frames,
            "n": n, "mean": round(mean, 2), "std": round(std, 2),
            "osc_per_s": round(zc / max(1e-6, args.duration), 1),
            "in10": round(in10, 3), "infer_fps": getattr(val, 'fps', None),
        }
        with open(os.path.join(args.out, "lock_quality.json"), "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print("[lq] result:", json.dumps(result, ensure_ascii=False))
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
