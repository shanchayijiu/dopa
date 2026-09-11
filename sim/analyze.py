"""靶场离线分析：真值 vs 检测/预测，算出可量化指标用于调参。

用法:
  python -m sim.analyze --dir logs/range/20260101_120000
"""
from __future__ import annotations

import argparse
import bisect
import json
import os
from statistics import mean


def _load_jsonl(path):
    rows = []
    if not os.path.isfile(path):
        return rows
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def _percentile(values, p):
    if not values:
        return 0.0
    vs = sorted(values)
    k = max(0, min(len(vs) - 1, int(round((p / 100.0) * (len(vs) - 1)))))
    return vs[k]


def _nearest_truth(times, truths, t):
    if not times:
        return None
    idx = bisect.bisect_left(times, t)
    candidates = []
    if idx < len(times):
        candidates.append(idx)
    if idx - 1 >= 0:
        candidates.append(idx - 1)
    best = None
    best_dt = None
    for i in candidates:
        dt = abs(times[i] - t)
        if best_dt is None or dt < best_dt:
            best_dt = dt
            best = truths[i]
    return best, best_dt


def analyze(out_dir, match_thresh=None, tol=0.1):
    meta = {}
    meta_path = os.path.join(out_dir, "meta.json")
    if os.path.isfile(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
    width = float(meta.get("width", 320))
    if match_thresh is None:
        match_thresh = width * 0.2

    truths = _load_jsonl(os.path.join(out_dir, "truth.jsonl"))
    overlays = _load_jsonl(os.path.join(out_dir, "overlay.jsonl"))
    events = _load_jsonl(os.path.join(out_dir, "events.jsonl"))

    times = [r["t"] for r in truths]
    box_errors = []
    count_errors = []
    matched_frames = 0
    frames_with_det = 0
    id_switches = 0
    last_track = None
    used = 0

    for ov in overlays:
        t = ov.get("t")
        if t is None:
            continue
        found = _nearest_truth(times, truths, t)
        if not found:
            continue
        truth, dt = found
        if dt is None or dt > tol:
            continue
        used += 1
        in_w = float(ov.get("input_w") or width) or width
        k = width / in_w
        dets = []
        for b in ov.get("boxes") or []:
            if b and len(b) >= 2:
                dets.append((b[0] * k, b[1] * k, b[2] * k if len(b) > 2 else 0.0))
        if dets:
            frames_with_det += 1
        targets = truth.get("targets") or []
        count_errors.append(abs(len(dets) - len(targets)))
        frame_errors = []
        for tg in targets:
            tx, ty = tg["x"], tg["y"]
            best = None
            best_d = 1e18
            for dx, dy, _dw in dets:
                d = (dx - tx) ** 2 + (dy - ty) ** 2
                if d < best_d:
                    best_d = d
                    best = (dx, dy)
            if best is not None and best_d ** 0.5 <= match_thresh:
                frame_errors.append(best_d ** 0.5)
        if frame_errors:
            matched_frames += 1
            box_errors.extend(frame_errors)
        trk = ov.get("track_id")
        if trk is not None:
            if last_track is not None and trk != last_track:
                id_switches += 1
            last_track = trk

    clicks = [e for e in events if e.get("kind") == "click"]
    hits = [e for e in clicks if e.get("hit")]

    total_targets = sum(len((r.get("targets") or [])) for r in truths)
    metrics = {
        "truth_frames": len(truths),
        "overlay_frames": len(overlays),
        "aligned_frames": used,
        "detection_rate": round(frames_with_det / used, 4) if used else 0.0,
        "match_rate": round(matched_frames / used, 4) if used else 0.0,
        "mean_box_error_px": round(mean(box_errors), 2) if box_errors else None,
        "p95_box_error_px": round(_percentile(box_errors, 95), 2) if box_errors else None,
        "mean_det_count_error": round(mean(count_errors), 3) if count_errors else None,
        "id_switches": id_switches,
        "truth_targets_total": total_targets,
        "clicks": len(clicks),
        "hits": len(hits),
        "hit_rate": round(len(hits) / len(clicks), 4) if clicks else None,
    }
    return metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True)
    parser.add_argument("--match-thresh", type=float, default=None)
    parser.add_argument("--tol", type=float, default=0.1)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    metrics = analyze(args.dir, args.match_thresh, args.tol)
    text = json.dumps(metrics, ensure_ascii=False, indent=2)
    print(text)
    out = args.out or os.path.join(args.dir, "metrics.json")
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"\n已写入: {out}")


if __name__ == "__main__":
    main()
