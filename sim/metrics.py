"""动态目标追踪的锁定质量指标（基于靶场/回放真值）。"""
from __future__ import annotations


def _percentile(values, p):
    if not values:
        return 0.0
    vs = sorted(values)
    k = max(0, min(len(vs) - 1, int(round((p / 100.0) * (len(vs) - 1)))))
    return vs[k]


def lock_metrics(errors, fps=100.0, e_lock=15.0, lock_frames=5, settle_frames=10):
    """从逐帧屏幕误差序列计算锁定质量。

    Args:
        errors: 每帧“目标中心 - 屏幕中心”的距离(px)。
        fps: 帧率，用于把帧序换算成时间。
        e_lock: 判定“已锁定”的误差阈值(px)。
        lock_frames: 连续多少帧都在阈值内才算锁定建立。
        settle_frames: 锁定后再跳过的帧数，用于统计稳态误差。

    Returns:
        dict: t_lock(秒, None=未锁定), e_med, e_p95, loss_rate, locked
    """
    n = len(errors)
    if n == 0:
        return {"t_lock": None, "e_med": None, "e_p95": None, "loss_rate": 1.0, "locked": False}

    lock_idx = None
    run = 0
    for i, e in enumerate(errors):
        if e <= e_lock:
            run += 1
            if run >= lock_frames:
                lock_idx = i - lock_frames + 1
                break
        else:
            run = 0

    if lock_idx is None:
        steady = errors[-max(1, int(fps)):]
        return {
            "t_lock": None,
            "e_med": round(float(_median(steady)), 2),
            "e_p95": round(float(_percentile(steady, 95)), 2),
            "loss_rate": 1.0,
            "locked": False,
        }

    start = min(n - 1, lock_idx + max(0, int(settle_frames)))
    steady = errors[start:] or errors[-1:]
    loss = sum(1 for e in steady if e > e_lock * 2.0) / max(1, len(steady))
    return {
        "t_lock": round(lock_idx / float(fps), 3),
        "e_med": round(float(_median(steady)), 2),
        "e_p95": round(float(_percentile(steady, 95)), 2),
        "loss_rate": round(loss, 4),
        "locked": True,
    }


def _median(values):
    vs = sorted(values)
    m = len(vs) // 2
    if len(vs) % 2:
        return vs[m]
    return (vs[m - 1] + vs[m]) / 2.0


def speed_sweep_report(results):
    """把一组 (speed, metrics) 汇总成“速度-锁定”表，并可求拐点。"""
    rows = []
    v_max = None
    for speed, m in sorted(results, key=lambda r: r[0]):
        row = {"speed": speed, **m}
        rows.append(row)
        if m.get("locked") and m.get("loss_rate", 1.0) < 0.1 and m.get("e_p95", 1e9) <= 25.0:
            v_max = speed
    return rows, v_max
