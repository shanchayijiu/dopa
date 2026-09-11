"""目标选择器多目标测试：多目标同时出现时，统计选中目标的切换次数。

目的：验证"目标选择器"能否抑制频繁切目标（黏性/锁定时间/ID强锁）。
用法:
  python tools/target_switch_test.py --count 3 --speed 200 --duration 12
  python tools/target_switch_test.py --sticky 120 --lock-ms 500
  python tools/target_switch_test.py --switch-delay 300
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=3)
    ap.add_argument("--speed", type=float, default=200.0)
    ap.add_argument("--duration", type=float, default=12.0)
    ap.add_argument("--sticky", type=float, default=None, help="target_sticky_pixels")
    ap.add_argument("--lock-ms", dest="lock_ms", type=float, default=None)
    ap.add_argument("--switch-delay", dest="switch_delay", type=float, default=None)
    ap.add_argument("--id-lock", dest="id_lock", default=None, choices=["on", "off"])
    ap.add_argument("--no-tracker", dest="no_tracker", action="store_true")
    ap.add_argument("--motion", default="bounce")
    ap.add_argument("--classes", default="32,29")
    ap.add_argument("--out", default=os.path.join("logs", "target_switch"))
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    classes = [int(x) for x in args.classes.split(",") if x.strip()]

    from sim.virtual_game import VirtualGame, set_shared_game
    from tools.track_speed_sweep import make_range_group

    game = VirtualGame(mode=args.motion, count=args.count, class_ids=tuple(classes),
                       show=False, out_dir=None)
    game.sim.set_target_speed(args.speed)
    set_shared_game(game)
    game.start()

    import cv2
    val = None
    try:
        from core import Valorant
        val = Valorant()
        cfg = val.config
        cfg['groups']['range'] = make_range_group(classes, 0.40, 1.0, 0.001, 8.0)
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
        cfg['is_curve'] = False
        cfg['is_curve_uniform'] = False
        cfg['kalman'] = {'enabled': True, 'predict_frames': 5, 'predict_gain': 1.0,
                         'process_noise': 0.5, 'measurement_noise': 15.0}
        if args.sticky is not None:
            cfg['target_sticky_pixels'] = args.sticky
        if args.lock_ms is not None:
            cfg['target_lock_ms'] = args.lock_ms
        if args.id_lock is not None:
            cfg['target_id_lock_enabled'] = (args.id_lock == "on")
        if args.switch_delay is not None:
            cfg['groups']['range']['aim_keys']['mouse_left']['target_switch_delay'] = int(args.switch_delay)
        if args.no_tracker:
            cfg['groups']['range']['aim_keys']['mouse_left']['tracker_enabled'] = False
        val.refresh_controller_params()
        val.refresh_engine()
        if val.engine is None:
            print('[ts] 引擎未加载')
            return 3
        val.running = True
        val.end = False
        if not val.go():
            print('[ts] go() 失败')
            return 4
        val.aim_key_status = True

        ids = []
        t_end = time.time() + args.duration
        while time.time() < t_end:
            ids.append(getattr(val.aim_pipeline, '_last_output_target_id', None))
            time.sleep(0.01)

        switches = 0
        prev = None
        seg = 0
        seglens = []
        for i in ids:
            if i is None:
                continue
            if prev is not None and i != prev:
                switches += 1
                seglens.append(seg)
                seg = 0
            prev = i
            seg += 1
        if seg:
            seglens.append(seg)
        result = {
            "count": args.count, "speed": args.speed, "duration": args.duration,
            "sticky": cfg.get('target_sticky_pixels'), "lock_ms": cfg.get('target_lock_ms'),
            "id_lock": cfg.get('target_id_lock_enabled'),
            "switch_delay": cfg['groups']['range']['aim_keys']['mouse_left'].get('target_switch_delay'),
            "samples": len(ids), "switches": switches,
            "switch_per_s": round(switches / max(1e-6, args.duration), 1),
            "seg_med": (sorted(seglens)[len(seglens)//2] if seglens else 0),
        }
        with open(os.path.join(args.out, "switch_result.json"), "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print("[ts] result:", json.dumps(result, ensure_ascii=False))
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


if __name__ == "__main__":
    sys.exit(main())
