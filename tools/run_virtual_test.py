"""虚拟靶场单机测试：起"虚拟游戏"小窗口，跑原生 app，验证动态追踪。

- 原生逻辑一行不改：infer / aim_bot_func / AimPipeline / execute_move 全部照跑；
- 只把两个 I/O 换成虚拟的：截图源=虚拟游戏帧，鼠标输出=虚拟游戏.move（不动真实鼠标）；
- 靶场小窗口里可见：中心准星随原生 pipeline 输出把球吸附到中心。

用法:
  python tools/run_virtual_test.py --duration 10 --speed 320
  python tools/run_virtual_test.py --duration 10 --mode brownian --count 2
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=float, default=10.0)
    ap.add_argument("--speed", type=float, default=320.0)
    ap.add_argument("--mode", default="bounce")
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--classes", default="32,29")
    ap.add_argument("--out", default=os.path.join("logs", "virtual_range"))
    ap.add_argument("--no-window", action="store_true")
    ap.add_argument("--no-kalman", action="store_true")
    ap.add_argument("--debug", action="store_true")
    ap.add_argument("--key", default=None, help="指定 aim_key，默认取 kp 最大者")
    ap.add_argument("--kp", type=float, default=None, help="诊断：临时覆盖 PID kp")
    ap.add_argument("--ki", type=float, default=None, help="诊断：临时覆盖 PID ki")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    classes = [int(x) for x in args.classes.split(",") if x.strip()]

    from sim.virtual_game import VirtualGame, set_shared_game, ensure_window
    from sim.metrics import lock_metrics

    game = VirtualGame(mode=args.mode, count=args.count, class_ids=tuple(classes),
                       show=not args.no_window, out_dir=args.out,
                       sens=1.0)
    # 让默认速度落在期望值附近
    game.sim.min_speed = max(60.0, args.speed * 0.8)
    game.sim.max_speed = args.speed
    set_shared_game(game)
    game.start()

    val = None
    try:
        from core import Valorant
        val = Valorant()
        cfg = val.config
        cfg['virtual_test'] = True
        cfg['single_machine_mode'] = False
        cfg['infer_debug'] = False
        cfg['print_fps'] = False
        cfg['inference_device'] = 'DML'
        cfg.setdefault('target_id_lock_enabled', True)
        cfg.setdefault('kalman', {})['enabled'] = not args.no_kalman

        grp = cfg['groups'][val.group]
        model = os.path.join('models', 'yolov8n_320.onnx')
        grp['infer_model'] = model
        grp['original_infer_model'] = model
        grp['is_v8'] = True
        grp['is_trt'] = False
        grp['model_variant'] = 'onnx'

        keys = list(grp.get('aim_keys', {}).keys())
        if not keys:
            print('[vt] 当前组没有 aim_keys，无法激活瞄准')
            return 2
        if args.key and args.key in grp['aim_keys']:
            key = args.key
        else:
            def _kp(k):
                try:
                    return float(grp['aim_keys'][k].get('pid_kp_x', 0) or 0)
                except Exception:
                    return 0.0
            key = max(keys, key=_kp)
        print("[vt] aim_keys:", {k: grp['aim_keys'][k].get('pid_kp_x') for k in keys},
              "-> 使用", key)
        grp['aim_keys'][key]['classes'] = list(classes)
        if args.kp is not None or args.ki is not None:
            for ax in ('x', 'y'):
                if args.kp is not None:
                    grp['aim_keys'][key][f'pid_kp_{ax}'] = args.kp
                if args.ki is not None:
                    grp['aim_keys'][key][f'pid_ki_{ax}'] = args.ki
            print(f"[vt] 诊断覆盖 PID: kp={args.kp} ki={args.ki}")
        trig = grp['aim_keys'][key].get('trigger')
        if isinstance(trig, dict):
            trig['status'] = False

        val.select_key = key
        val.old_pressed_aim_key = key
        val.pressed_key_config = val.aim_keys_dist[key]
        val.refresh_controller_params()

        val.refresh_engine()
        if val.engine is None:
            print('[vt] 引擎未加载，退出')
            return 3
        print(f"[vt] 引擎就绪: {model}  input={val.engine.get_input_shape()}")

        val.running = True
        val.end = False
        if not val.go():
            print('[vt] go() 失败')
            return 4

        val.aim_key_status = True

        if args.debug:
            kc = val.pressed_key_config
            print("[dbg] key cfg:", {k: kc.get(k) for k in
                  ('move_deadzone', 'pid_kp_x', 'pid_ki_x', 'pid_kd_x',
                   'pid_integral_limit_x', 'smooth_x', 'confidence_threshold')})
            print("[dbg] screen_center:", val.screen_center_x, val.screen_center_y,
                  "screen:", val.screen_width, val.screen_height)
            _orig_move = game.move
            _moves = []
            def _logged_move(dx, dy):
                _moves.append((dx, dy))
                return _orig_move(dx, dy)
            game.move = _logged_move
            val.move_r = _logged_move
        else:
            _moves = None

        show = not args.no_window
        window = "virtual range"
        if show:
            ensure_window(window)
        errors = []
        app_errors = []
        import math as _math
        fps = 100.0
        dt = 1.0 / fps
        t_end = time.time() + args.duration
        t0 = time.time()
        while time.time() < t_end:
            errors.append(game.center_error())
            pos = getattr(val.aim_pipeline, '_last_output_target_pos', None)
            if pos is not None:
                app_errors.append(_math.hypot(pos[0] - val.screen_center_x, pos[1] - val.screen_center_y))
            if args.debug and len(errors) <= 20:
                snap = game.sim.snapshot()["targets"]
                bx = snap[0]["x"] if snap else None
                mv = _moves[-1] if _moves else None
                print(f"[dbg] i={len(errors)} ball_x={bx:.1f} app_pos={pos} "
                      f"app_err={app_errors[-1] if app_errors else None} move={mv}")
            if show:
                fr = game.get_frame()
                if fr is not None:
                    try:
                        cv2.imshow(window, fr)
                        cv2.waitKey(1)
                    except Exception:
                        show = False
            time.sleep(dt)
        elapsed = time.time() - t0
        if show:
            try:
                cv2.destroyWindow(window)
                cv2.waitKey(1)
            except Exception:
                pass

        m = lock_metrics(errors, fps)
        def _med(v):
            if not v:
                return None
            s = sorted(v); k = len(s) // 2
            return round(s[k] if len(s) % 2 else (s[k-1] + s[k]) / 2, 2)
        result = {
            "mode": "virtual_native", "duration": round(elapsed, 2), "samples": len(errors),
            "motion": args.mode, "count": args.count, "target_speed": args.speed,
            "kalman": not args.no_kalman, "infer_fps": getattr(val, 'fps', None),
            "game_err_med": _med(errors), "app_err_med": _med(app_errors), **m,
        }
        with open(os.path.join(args.out, "result.json"), "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print("[vt] result:", json.dumps(result, ensure_ascii=False))
        print(f"[vt] 视频: {os.path.join(args.out, 'virtual_range.avi')}")
        return 0
    finally:
        try:
            if val is not None:
                val.running = False
        except Exception:
            pass
        try:
            if val is not None and getattr(val, 'timer_id', 0):
                val.time_kill_event(val.timer_id)
                val.timer_id = 0
        except Exception:
            pass
        try:
            if val is not None:
                val.close_screenshot()
        except Exception:
            pass
        try:
            if val is not None:
                val._secure_cleanup()
        except Exception:
            pass
        game.stop()


if __name__ == "__main__":
    sys.exit(main())
