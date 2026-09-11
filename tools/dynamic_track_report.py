"""动态目标锁定质量速度扫描：输出速度-误差表与拐点 V_max。

用法:
  python tools/dynamic_track_report.py --speeds 100,200,300,400,500,600,800 --duration 4
  python tools/dynamic_track_report.py --both --out logs\track_sweep.csv
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sim.metrics import speed_sweep_report  # noqa: E402
from sim.replay import run_replay  # noqa: E402


def _parse_speeds(text):
    return [float(x) for x in text.replace(" ", "").split(",") if x]


def _run(speeds, motion, duration, use_kalman, seed):
    results = []
    for v in speeds:
        r = run_replay(v, motion=motion, duration=duration, use_kalman=use_kalman, seed=seed)
        results.append((v, r.metrics()))
    return results


def _print_table(title, rows, v_max):
    print(f"\n== {title} ==")
    print(f"{'速度(px/s)':>10} {'锁定':>6} {'T_lock(s)':>10} {'e_med':>8} {'e_p95':>8} {'丢失率':>8}")
    for row in rows:
        locked = "是" if row.get("locked") else "否"
        print(f"{row['speed']:>10.0f} {locked:>6} "
              f"{'-' if row.get('t_lock') is None else row['t_lock']:>10} "
              f"{row.get('e_med')!s:>8} {row.get('e_p95')!s:>8} {row.get('loss_rate')!s:>8}")
    print(f"V_max(锁定拐点) ≈ {v_max}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--speeds", default="100,200,300,400,500,600,800")
    parser.add_argument("--motion", default="linear", choices=["linear", "brownian", "teleport"])
    parser.add_argument("--duration", type=float, default=4.0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--both", action="store_true", help="同时对比预测开/关")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    speeds = _parse_speeds(args.speeds)
    all_rows = []

    rows_on, vmax_on = speed_sweep_report(_run(speeds, args.motion, args.duration, True, args.seed))
    _print_table(f"{args.motion} / Kalman开", rows_on, vmax_on)
    for row in rows_on:
        all_rows.append({"kalman": 1, **row})

    if args.both:
        rows_off, vmax_off = speed_sweep_report(_run(speeds, args.motion, args.duration, False, args.seed))
        _print_table(f"{args.motion} / Kalman关", rows_off, vmax_off)
        for row in rows_off:
            all_rows.append({"kalman": 0, **row})

        print(f"\n== {args.motion} / 预测开 vs 关（e_med px）==")
        print(f"{'速度':>8} {'开':>8} {'关':>8} {'改善':>8}")
        off_by_speed = {r["speed"]: r for r in rows_off}
        for r in rows_on:
            o = off_by_speed.get(r["speed"])
            on_med = r.get("e_med")
            off_med = o.get("e_med") if o else None
            if on_med is None or off_med is None:
                print(f"{r['speed']:>8.0f} {on_med!s:>8} {off_med!s:>8} {'-':>8}")
                continue
            delta = off_med - on_med
            print(f"{r['speed']:>8.0f} {on_med:>8} {off_med:>8} {delta:>+8.1f}")

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        keys = ["kalman", "speed", "locked", "t_lock", "e_med", "e_p95", "loss_rate"]
        with open(args.out, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            for row in all_rows:
                w.writerow({k: row.get(k) for k in keys})
        print(f"\n已写入: {args.out}")


if __name__ == "__main__":
    main()
