"""闪现（瞬移）目标锁定测试：目标每隔一段时间瞬间跳到新位置，测重新锁定能力。

用法:
  python tools/blink_lock_test.py --speed 200 --blink-interval 1.0 --blink-dist 120 --duration 20
  python tools/blink_lock_test.py --no-kalman --blink-interval 0.8
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
    ap.add_argument("--speed", type=float, default=200.0)
    ap.add_argument("--blink-interval", dest="blink_interval", type=float, default=1.0)
    ap.add_argument("--blink-dist", dest="blink_dist", type=float, default=120.0)
    ap.add_argument("--duration", type=float, default=20.0)
    ap.add_argument("--relock-px", dest="relock_px", type=float, default=15.0)
    ap.add_argument("--lock-hold", dest="lock_hold", type=int, default=3)
    ap.add_argument("--max-wait", dest="max_wait", type=float, default=1.0)
    ap.add_argument("--jump-thresh", dest="jump_thresh", type=float, default=50.0)
    ap.add_argument("--classes", default="32,29")
    ap.add_argument("--kp", type=float, default=0.35)
    ap.add_argument("--ki", type=float, default=1.0)
    ap.add_argument("--kd", type=float, default=0.001)
    ap.add_argument("--predict-gain", type=float, default=1.0)
    ap.add_argument("--predict-frames", type=int, default=5)
    ap.add_argument("--min-lead-speed", dest="min_lead_speed", type=float, default=60.0)
    ap.add_argument("--max-lead", dest="max_lead", type=float, default=40.0)
    ap.add_argument("--lead-smooth", dest="lead_smooth", type=float, default=0.18)
    ap.add_argument("--no-kalman", action="store_true")
    ap.add_argument("--window", action="store_true")
    ap.add_argument("--out", default=os.path.join("logs", "blink_lock"))
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    classes = [int(x) for x in args.classes.split(",") if x.strip()]

    from sim.virtual_game import VirtualGame, set_shared_game, ensure_window
    from tools.track_speed_sweep import make_range_group

    game = VirtualGame(mode="blink", count=1, class_ids=tuple(classes),
                       show=bool(args.window), out_dir=(args.out if args.window else None))
    game.sim.blink_interval = args.blink_interval
    game.sim.blink_dist = args.blink_dist
    if game.sim._targets:
        game.sim._targets[0].timer = args.blink_interval
    game.sim.set_target_speed(args.speed)
    set_shared_game(game)
    game.start()

    import cv2
    if args.window:
        ensure_window("blink lock")
    val = None
    try:
        from core import Valorant
        val = Valorant()
        cfg = val.config
        cfg['groups']['range'] = make_range_group(classes, args.kp, args.ki, args.kd, 8.0)
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
        cfg['kalman'] = {
            'enabled': not args.no_kalman, 'predict_frames': args.predict_frames,
            'predict_gain': args.predict_gain, 'process_noise': 0.5, 'measurement_noise': 15.0,
        }
        val.refresh_controller_params()
        val.refresh_engine()
        if val.engine is None:
            print('[blink] 引擎未加载')
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
            print('[blink] go() 失败')
            return 4
        val.aim_key_status = True

        samples = []  # (abs_t, bx, by, err)
        fps = 100.0
        dt = 1.0 / fps
        t_end = time.time() + args.duration
        run_start = time.time()
        while time.time() < t_end:
            snap = game.sim.snapshot()["targets"]
            if snap:
                samples.append((time.time(), snap[0]["x"], snap[0]["y"], game.center_error()))
            if args.window:
                fr = game.get_frame()
                if fr is not None:
                    cv2.imshow("blink lock", fr)
                    cv2.waitKey(1)
            time.sleep(dt)

        # 直接用仿真记录的闪现事件（避免被自运动平移误判）
        blink_times = [t for t in game.sim.blink_events if run_start <= t <= time.time()]
        sample_times = [s[0] for s in samples]

        def _first_index_after(bt):
            lo, hi = 0, len(sample_times)
            while lo < hi:
                mid = (lo + hi) // 2
                if sample_times[mid] < bt:
                    lo = mid + 1
                else:
                    hi = mid
            return lo

        lat = []
        success = 0
        for bt in blink_times:
            start = _first_index_after(bt)
            hold = 0
            for j in range(start, len(samples)):
                if samples[j][0] - bt > args.max_wait:
                    break
                if samples[j][3] <= args.relock_px:
                    hold += 1
                    if hold >= args.lock_hold:
                        lat.append(round((samples[j][0] - bt) * 1000.0, 1))
                        success += 1
                        break
                else:
                    hold = 0
        steady = [s[3] for s in samples
                  if all(abs(s[0] - bt) > args.max_wait for bt in blink_times)]
        in20 = sum(1 for e in steady if e <= 20.0) / max(1, len(steady))

        def med(v):
            if not v:
                return None
            s = sorted(v)
            k = len(s) // 2
            return round(s[k] if len(s) % 2 else (s[k - 1] + s[k]) / 2, 1)

        result = {
            "mode": "blink", "speed": args.speed, "blink_interval": args.blink_interval,
            "blink_dist": args.blink_dist, "kalman": not args.no_kalman,
            "samples": len(samples), "blinks": len(blink_times),
            "relock_success": success,
            "relock_rate": round(success / max(1, len(blink_times)), 3),
            "relock_ms_med": med(lat),
            "relock_ms_p95": (sorted(lat)[max(0, int(0.95 * (len(lat) - 1)))] if lat else None),
            "steady_in20": round(in20, 3), "infer_fps": getattr(val, 'fps', None),
        }
        with open(os.path.join(args.out, "blink_result.json"), "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print("[blink] result:", json.dumps(result, ensure_ascii=False))
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
