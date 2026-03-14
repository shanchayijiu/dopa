# -*- coding: utf-8 -*-
"""
准星找色追踪模块 — 从 core.py 抽取的独立组件

职责：
  - HSV 颜色检测 + 形态学处理
  - 轮廓评分 + 目标选择
  - EMA 平滑 + 时间衰减
  - 回拉量计算（不直接操作鼠标）
  - 取色（纯计算，不操作 GUI）
"""
import time
import cv2
import numpy as np


class CrosshairTracker:
    """准星找色追踪器，无 GUI / 设备依赖"""

    def __init__(self):
        # ── 公开状态（core 读取） ──
        self.offset = (0.0, 0.0)
        self.lock_box = None
        self.debug_mask = None
        self.last_frame = None

        # ── EMA 平滑 ──
        self._ema_x = 0.0
        self._ema_y = 0.0
        self._ema_initialized = False

        # ── 目标粘滞 ──
        self._prev_target = None

        # ── 回拉去重 ──
        self._pull_seq = 0
        self._pull_consumed_seq = -1

        # ── 小目标 mask 累积 ──
        self._mask_accum = None
        self._mask_accum_count = 0

        # ── miss 宽限 ──
        self._miss_count = 0

        # ── 小模式迟滞 ──
        self._small_mode = False

        # ── 形态学核（复用） ──
        self._kern_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        self._kern_close = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        self._kern_dilate_s = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        self._kern_close_s = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))

        # ── HSV bounds 缓存 ──
        self._bounds_cache_key = None
        self._bounds_cache = []

        # ── 回拉参数缓存 ──
        self._pull_sig = None
        self._pull_params = None

        # ── 调试计数器 ──
        self._debug_counter = 0

        # ── 衰减时间戳 ──
        self._last_decay_time = time.perf_counter()

        # ── 像素计数（外部调试用） ──
        self._last_pixel_count = 0

        # ── 配置初始化标记 ──
        self._cfg_ensured = False

        # ── lock_box 平滑 ──
        self._box_ema = None  # (x1, y1, x2, y2) float

    # ────────────────────────────────────────────
    #  配置管理
    # ────────────────────────────────────────────

    def get_config(self, config):
        """从全局 config 中获取并确保 crosshair_color_lock 子配置完整"""
        cfg = config.get('crosshair_color_lock')
        if not isinstance(cfg, dict):
            cfg = {}
            config['crosshair_color_lock'] = cfg
        if not self._cfg_ensured:
            self._ensure_defaults(cfg)
            self._cfg_ensured = True
        if cfg.get('only_when_aiming') is None:
            cfg['only_when_aiming'] = True
        return cfg

    @staticmethod
    def _ensure_defaults(cfg):
        cfg.setdefault('enabled', False)
        cfg.setdefault('roi_width', 200)
        cfg.setdefault('roi_height', 200)
        cfg.setdefault('show_crosshair', True)
        cfg.setdefault('show_lock_box', True)
        cfg.setdefault('min_area', 5)
        cfg.setdefault('last_rgb', [0, 0, 0])
        cfg.setdefault('h_tolerance', 10)
        cfg.setdefault('s_tolerance', 40)
        cfg.setdefault('v_tolerance', 60)
        cfg.setdefault('ema_smooth', 0.4)
        cfg.setdefault('small_pixel_threshold', 150)
        cfg.setdefault('only_when_aiming', True)
        hsv_ranges = cfg.get('hsv_ranges')
        if not isinstance(hsv_ranges, list) or len(hsv_ranges) == 0:
            min_color = cfg.get('min_color', [0, 0, 0])
            max_color = cfg.get('max_color', [255, 255, 255])
            if (isinstance(min_color, list) and len(min_color) >= 3
                    and isinstance(max_color, list) and len(max_color) >= 3):
                bgr_min = np.array([[min_color[:3]]], dtype=np.uint8)
                bgr_max = np.array([[max_color[:3]]], dtype=np.uint8)
                hsv_min = cv2.cvtColor(bgr_min, cv2.COLOR_BGR2HSV)[0][0]
                hsv_max = cv2.cvtColor(bgr_max, cv2.COLOR_BGR2HSV)[0][0]
                cfg['hsv_ranges'] = [{
                    'h_min': int(min(hsv_min[0], hsv_max[0])),
                    'h_max': int(max(hsv_min[0], hsv_max[0])),
                    's_min': int(min(hsv_min[1], hsv_max[1])),
                    's_max': int(max(hsv_min[1], hsv_max[1])),
                    'v_min': int(min(hsv_min[2], hsv_max[2])),
                    'v_max': int(max(hsv_min[2], hsv_max[2])),
                }]
            else:
                cfg['hsv_ranges'] = [{'h_min': 0, 'h_max': 179, 's_min': 0,
                                      's_max': 255, 'v_min': 0, 'v_max': 255}]
        if not isinstance(cfg.get('active_index'), int):
            cfg['active_index'] = 0
        if cfg['active_index'] < 0 or cfg['active_index'] >= len(cfg['hsv_ranges']):
            cfg['active_index'] = 0

    # ────────────────────────────────────────────
    #  HSV 工具
    # ────────────────────────────────────────────

    @staticmethod
    def normalize_hsv_value(value, min_val, max_val, default):
        try:
            number = int(value)
        except Exception:
            number = int(default)
        return max(min_val, min(max_val, number))

    @classmethod
    def normalize_hsv_range(cls, hsv_range):
        if not isinstance(hsv_range, dict):
            hsv_range = {}
        nv = cls.normalize_hsv_value
        h_min = nv(hsv_range.get('h_min', 0), 0, 179, 0)
        h_max = nv(hsv_range.get('h_max', 179), 0, 179, 179)
        s_min = nv(hsv_range.get('s_min', 0), 0, 255, 0)
        s_max = nv(hsv_range.get('s_max', 255), 0, 255, 255)
        v_min = nv(hsv_range.get('v_min', 0), 0, 255, 0)
        v_max = nv(hsv_range.get('v_max', 255), 0, 255, 255)
        if s_max < s_min:
            s_min, s_max = s_max, s_min
        if v_max < v_min:
            v_min, v_max = v_max, v_min
        return {'h_min': h_min, 'h_max': h_max,
                's_min': s_min, 's_max': s_max,
                'v_min': v_min, 'v_max': v_max}

    # ────────────────────────────────────────────
    #  核心：每帧更新
    # ────────────────────────────────────────────

    def update(self, frame, cfg):
        """主检测入口，在 infer 线程每帧调用"""
        self.last_frame = frame
        if not cfg.get('enabled'):
            self.offset = (0.0, 0.0)
            self.lock_box = None
            self._ema_initialized = False
            self._prev_target = None
            self._mask_accum = None
            self._mask_accum_count = 0
            self._miss_count = 0
            self._small_mode = False
            self._box_ema = None
            return

        h, w = frame.shape[:2]
        roi_w = max(1, min(int(cfg.get('roi_width', 200)), w))
        roi_h = max(1, min(int(cfg.get('roi_height', 200)), h))
        cx, cy = w // 2, h // 2
        x1 = max(0, cx - roi_w // 2)
        y1 = max(0, cy - roi_h // 2)
        x2 = min(w, x1 + roi_w)
        y2 = min(h, y1 + roi_h)
        roi = frame[y1:y2, x1:x2]

        # 不做高斯模糊：准星是 1-2px 细线，模糊会把准星色和背景混合导致丢失
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        # ── HSV bounds 缓存 ──
        hsv_ranges = cfg.get('hsv_ranges', [])
        show_active_only = cfg.get('show_active_only', False)
        active_index = int(cfg.get('active_index', 0))
        h_tol = int(cfg.get('h_tolerance', 10))
        s_tol = int(cfg.get('s_tolerance', 30))
        v_tol = int(cfg.get('v_tolerance', 30))

        ranges_sig = tuple(
            (r.get('h_min'), r.get('h_max'), r.get('s_min'),
             r.get('s_max'), r.get('v_min'), r.get('v_max'),
             r.get('h_center'), r.get('s_center'), r.get('v_center'))
            for r in hsv_ranges if isinstance(r, dict)
        )
        cache_key = (ranges_sig, show_active_only, active_index, h_tol, s_tol, v_tol)
        if self._bounds_cache_key != cache_key:
            self._bounds_cache = self._build_bounds(
                hsv_ranges, show_active_only, active_index, h_tol, s_tol, v_tol)
            self._bounds_cache_key = cache_key
        cached = self._bounds_cache

        # ── inRange ──
        mask = None
        for entry in cached:
            if entry is None:
                continue
            _, lo1, hi1, lo2, hi2 = entry
            if lo2 is not None:
                cm = cv2.bitwise_or(cv2.inRange(hsv, lo1, hi1),
                                    cv2.inRange(hsv, lo2, hi2))
            else:
                cm = cv2.inRange(hsv, lo1, hi1)
            mask = cm if mask is None else cv2.bitwise_or(mask, cm)

        # ── 形态学 ──
        if mask is not None:
            pixel_count = cv2.countNonZero(mask)
            self._last_pixel_count = pixel_count
            small_thresh = int(cfg.get('small_pixel_threshold', 150))

            # Use center-region pixel count for small_mode determination.
            # Prevents background noise at ROI edges (common with green)
            # from inflating the count and incorrectly exiting small_mode.
            mh, mw = mask.shape[:2]
            mx, my = max(1, mw // 4), max(1, mh // 4)
            if mw > 4 and mh > 4:
                center_count = cv2.countNonZero(mask[my:mh - my, mx:mw - mx])
            else:
                center_count = pixel_count

            if self._small_mode:
                is_small = center_count <= int(small_thresh * 1.4)
            else:
                is_small = center_count <= small_thresh
            self._small_mode = is_small

            if is_small:
                mask = cv2.dilate(mask, self._kern_dilate_s, iterations=1)
                mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self._kern_close_s, iterations=1)
                # 多帧累积
                if self._mask_accum is not None and self._mask_accum.shape == mask.shape:
                    self._mask_accum = cv2.addWeighted(self._mask_accum, 0.5, mask, 0.5, 0)
                    _, mc = cv2.threshold(self._mask_accum, 80, 255, cv2.THRESH_BINARY)
                    mask = cv2.bitwise_or(mask, mc)
                else:
                    self._mask_accum = mask.copy()
                self._mask_accum_count += 1
            else:
                # 非小目标模式的形态学处理
                density = pixel_count / max(1, mw * mh)
                if density > 0.08:
                    # 高密度噪声：用 OPEN 去噪，强度随密度增加
                    open_iter = 2 if density > 0.15 else 1
                    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self._kern_open, iterations=open_iter)
                # 所有情况都做 CLOSE 连接断裂像素
                mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self._kern_close, iterations=1)
                # Lightweight temporal smoothing to stabilize mask across frames
                if self._mask_accum is not None and self._mask_accum.shape == mask.shape:
                    self._mask_accum = cv2.addWeighted(self._mask_accum, 0.3, mask, 0.7, 0)
                    _, mc = cv2.threshold(self._mask_accum, 100, 255, cv2.THRESH_BINARY)
                    mask = mc
                else:
                    self._mask_accum = mask.copy()
                self._mask_accum_count = 0

        # ── 调试日志 ──
        self._debug_counter += 1
        show_debug = cfg.get('show_debug_log', False)
        should_log = show_debug and (self._debug_counter % 60 == 0)

        if mask is None:
            self.debug_mask = None
            if should_log:
                print("准星找色: 未配置颜色范围")
            self.offset = (0.0, 0.0)
            self.lock_box = None
            self._ema_initialized = False
            self._prev_target = None
            return

        # ── 调试图 ──
        debug_img = None
        if cfg.get('show_mask', False):
            debug_img = np.zeros_like(frame)
            rf = cv2.bitwise_and(roi, roi, mask=mask)
            rh, rw = rf.shape[:2]
            debug_img[y1:y1 + rh, x1:x1 + rw] = rf
            self.debug_mask = debug_img
        else:
            self.debug_mask = None

        if should_log:
            cv2.countNonZero(mask)  # kept for log parity

        # ── 轮廓 ──
        ci = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = ci[0] if len(ci) == 2 else ci[1]
        if not contours:
            if should_log:
                print("准星找色: 未找到轮廓 (匹配像素可能太少)")
            self._miss_count += 1
            if self._miss_count >= 15:
                self._decay(cfg)
            return

        min_area = max(1.0, float(cfg.get('min_area', 1.0)))
        max_area = float(cfg.get('max_area', 1000.0))
        actual_w = x2 - x1
        actual_h = y2 - y1
        roi_cx = actual_w / 2.0
        roi_cy = actual_h / 2.0
        max_dist_sq = max(1.0, roi_cx * roi_cx + roi_cy * roi_cy)

        valid = self._filter_contours(contours, min_area, max_area,
                                      self._small_mode, roi_cx, roi_cy)

        if self._small_mode and len(valid) > 1:
            md = max(actual_w, actual_h) * 0.08
            merged = self._merge_nearby(valid, md * md, roi_cx, roi_cy)
            if merged:
                valid = merged

        if not valid:
            if should_log:
                print("准星找色: 没有符合条件的轮廓")
            self._miss_count += 1
            if self._miss_count >= 15:
                self._decay(cfg)
            return

        # ── 多轮廓时补 solidity ──
        if len(valid) > 1:
            for idx, (cnt, ds, area, rect, center, _) in enumerate(valid):
                hull = cv2.convexHull(cnt)
                ha = cv2.contourArea(hull)
                valid[idx] = (cnt, ds, area, rect, center, area / ha if ha > 0 else 0.0)

        # ── 评分选最佳 ──
        best = self._score_contours(valid, max_dist_sq, self._prev_target,
                                    max(actual_w, actual_h))
        _, _, area, (bx, by, bw, bh), (cx_roi, cy_roi), _ = best
        # Smooth _prev_target with EMA to stabilize contour selection
        if self._prev_target is not None:
            pt_alpha = 0.4
            self._prev_target = (
                self._prev_target[0] + pt_alpha * (cx_roi - self._prev_target[0]),
                self._prev_target[1] + pt_alpha * (cy_roi - self._prev_target[1]),
            )
        else:
            self._prev_target = (cx_roi, cy_roi)

        box = (x1 + bx, y1 + by, x1 + bx + bw, y1 + by + bh)
        # Smooth lock_box with EMA to prevent ±1 pixel jitter
        box_alpha = 0.35
        if self._box_ema is None:
            self._box_ema = (float(box[0]), float(box[1]), float(box[2]), float(box[3]))
        else:
            self._box_ema = (
                self._box_ema[0] + box_alpha * (box[0] - self._box_ema[0]),
                self._box_ema[1] + box_alpha * (box[1] - self._box_ema[1]),
                self._box_ema[2] + box_alpha * (box[2] - self._box_ema[2]),
                self._box_ema[3] + box_alpha * (box[3] - self._box_ema[3]),
            )
        self.lock_box = (
            int(round(self._box_ema[0])), int(round(self._box_ema[1])),
            int(round(self._box_ema[2])), int(round(self._box_ema[3])),
        )
        cross_x = x1 + cx_roi
        cross_y = y1 + cy_roi

        if debug_img is not None:
            cv2.circle(debug_img, (int(cross_x), int(cross_y)), 2, (255, 0, 0), -1)

        raw_dx = cross_x - w / 2.0
        raw_dy = cross_y - h / 2.0

        # ── 自适应 EMA ──
        ema_base = max(0.05, min(1.0, float(cfg.get('ema_smooth', 0.4))))
        mag = abs(raw_dx) + abs(raw_dy)
        if mag > 30.0:
            alpha = min(0.7, ema_base * 1.5)
        elif mag > 10.0:
            alpha = ema_base
        else:
            alpha = max(0.05, ema_base * 0.5)

        if not self._ema_initialized:
            self._ema_x = raw_dx
            self._ema_y = raw_dy
            self._ema_initialized = True
        else:
            self._ema_x += alpha * (raw_dx - self._ema_x)
            self._ema_y += alpha * (raw_dy - self._ema_y)

        self.offset = (self._ema_x, self._ema_y)
        self._pull_seq += 1
        self._miss_count = 0
        self._last_decay_time = time.perf_counter()

        if should_log and (abs(self._ema_x) > 1.0 or abs(self._ema_y) > 1.0):
            print(f"准星找色: 锁定目标 area={area:.1f}, solidity={best[5]:.2f}, "
                  f"offset=({self._ema_x:.1f}, {self._ema_y:.1f})")

    # ────────────────────────────────────────────
    #  衰减 & 回拉
    # ────────────────────────────────────────────

    def _decay(self, cfg):
        """目标丢失时平滑衰减偏移量（帧率无关）"""
        if self._ema_initialized:
            now = time.perf_counter()
            dt = now - self._last_decay_time
            self._last_decay_time = now
            decay = 0.5 ** (dt / 0.1) if dt > 0 else 0.7
            self._ema_x *= decay
            self._ema_y *= decay
            if abs(self._ema_x) < 0.3 and abs(self._ema_y) < 0.3:
                self._ema_x = 0.0
                self._ema_y = 0.0
                self._ema_initialized = False
                self._prev_target = None
            self.offset = (self._ema_x, self._ema_y)
            self._pull_seq += 1
        else:
            self.offset = (0.0, 0.0)
        self.lock_box = None
        self._box_ema = None

    def try_pull(self, cfg, fallback_deadzone=1.0):
        """计算回拉移动量，返回 (dx, dy) 或 None（不直接操作鼠标）"""
        seq = self._pull_seq
        if seq == self._pull_consumed_seq:
            return None
        self._pull_consumed_seq = seq
        dx, dy = self.offset

        sig = (cfg.get('pull_deadzone'), cfg.get('pull_k'), cfg.get('pull_max_speed'))
        if self._pull_sig != sig:
            try:
                dz = float(cfg.get('pull_deadzone', fallback_deadzone))
            except Exception:
                dz = fallback_deadzone
            try:
                k = float(cfg.get('pull_k', 0.12))
            except Exception:
                k = 0.12
            try:
                ms = float(cfg.get('pull_max_speed', 6.0))
            except Exception:
                ms = 6.0
            self._pull_params = (dz, k, ms)
            self._pull_sig = sig

        deadzone, pull_k, max_speed = self._pull_params
        if max_speed <= 0:
            return None
        if abs(dx) <= deadzone and abs(dy) <= deadzone:
            return None
        mx = max(-max_speed, min(max_speed, dx * pull_k))
        my = max(-max_speed, min(max_speed, dy * pull_k))
        if abs(mx) > deadzone or abs(my) > deadzone:
            return (mx, my)
        return None

    # ────────────────────────────────────────────
    #  取色（纯计算）
    # ────────────────────────────────────────────

    def pick_color(self, frame, cfg):
        """
        在画面中心区域取色，通过对比背景自动分离准星像素。
        返回 (new_hsv_range, rgb, hsv_values) 或 None
        """
        if frame is None:
            return None
        h, w = frame.shape[:2]
        cx, cy = w // 2, h // 2

        # 取较大区域用于背景参考
        half_bg = 8  # 17×17
        bx1 = max(0, cx - half_bg)
        bx2 = min(w, cx + half_bg + 1)
        by1 = max(0, cy - half_bg)
        by2 = min(h, cy + half_bg + 1)
        region = frame[by1:by2, bx1:bx2].astype(np.float32)
        if region.size == 0:
            return None

        rh, rw = region.shape[:2]
        rcx, rcy = rw // 2, rh // 2

        # 四角 3×3 作为背景参考（准星不可能在角落）
        cs = 3
        corners = np.concatenate([
            region[:cs, :cs].reshape(-1, 3),
            region[:cs, -cs:].reshape(-1, 3),
            region[-cs:, :cs].reshape(-1, 3),
            region[-cs:, -cs:].reshape(-1, 3),
        ])
        bg_color = np.median(corners, axis=0)

        # 中心 5×5 为准星候选区
        half_fg = 2
        fg = region[rcy - half_fg:rcy + half_fg + 1,
                     rcx - half_fg:rcx + half_fg + 1].reshape(-1, 3)

        # 找与背景色差最大的像素
        diffs = np.sqrt(np.sum((fg - bg_color) ** 2, axis=1))
        threshold = max(25.0, np.max(diffs) * 0.4)
        crosshair_mask = diffs > threshold

        if np.any(crosshair_mask):
            crosshair_pixels = fg[crosshair_mask]
        else:
            # 回退：取差异最大的单像素
            crosshair_pixels = fg[np.argmax(diffs):np.argmax(diffs) + 1]

        b, g, r = [int(np.median(crosshair_pixels[:, ch])) for ch in range(3)]
        hsv_pixel = np.uint8([[[b, g, r]]])
        hsv = cv2.cvtColor(hsv_pixel, cv2.COLOR_BGR2HSV)[0][0]
        h_val, s_val, v_val = int(hsv[0]), int(hsv[1]), int(hsv[2])

        h_tol = int(cfg.get('h_tolerance', 10))
        s_tol = int(cfg.get('s_tolerance', 40))
        v_tol = int(cfg.get('v_tolerance', 60))

        h_min = h_val - h_tol
        h_max = h_val + h_tol
        if h_min < 0:
            h_min += 180
        if h_max > 179:
            h_max -= 180
        s_min = max(0, min(255, s_val - s_tol))
        s_max = max(0, min(255, s_val + s_tol))
        v_min = max(0, min(255, v_val - v_tol))
        v_max = max(0, min(255, v_val + v_tol))

        new_range = {'h_min': h_min, 'h_max': h_max,
                     's_min': s_min, 's_max': s_max,
                     'v_min': v_min, 'v_max': v_max,
                     'h_center': h_val, 's_center': s_val, 'v_center': v_val}
        return new_range, (r, g, b), (h_val, s_val, v_val)

    def reset(self):
        """功能禁用时完整重置状态"""
        self.offset = (0.0, 0.0)
        self.lock_box = None
        self.debug_mask = None
        self._ema_x = 0.0
        self._ema_y = 0.0
        self._ema_initialized = False
        self._box_ema = None
        self._prev_target = None
        self._mask_accum = None
        self._mask_accum_count = 0
        self._miss_count = 0
        self._small_mode = False

    # ────────────────────────────────────────────
    #  内部方法
    # ────────────────────────────────────────────

    def _build_bounds(self, hsv_ranges, show_active_only, active_index,
                      h_tol=10, s_tol=30, v_tol=30):
        bounds = []
        for i, hr in enumerate(hsv_ranges):
            if show_active_only and i != active_index:
                bounds.append(None)
                continue
            # Recompute from center values if available, so tolerance
            # changes take effect without re-picking color
            if 'h_center' in hr:
                hc = int(hr['h_center'])
                sc = int(hr['s_center'])
                vc = int(hr['v_center'])
                h_lo = hc - h_tol
                h_hi = hc + h_tol
                if h_lo < 0:
                    h_lo += 180
                if h_hi > 179:
                    h_hi -= 180
                s_lo = max(0, sc - s_tol)
                s_hi = min(255, sc + s_tol)
                v_lo = max(0, vc - v_tol)
                v_hi = min(255, vc + v_tol)
                if sc > 80:
                    # 高饱和度准星：H 是主要区分手段，S/V 自动放宽以
                    # 捕获抗锯齿和混色的边缘像素（可到中心值的 35%）
                    auto_s_lo = max(15, int(sc * 0.35))
                    auto_v_lo = max(15, int(vc * 0.35))
                    s_lo = min(s_lo, auto_s_lo)
                    s_hi = 255
                    v_lo = min(v_lo, auto_v_lo)
                    v_hi = 255
            else:
                nr = self.normalize_hsv_range(hr)
                h_lo, h_hi = nr['h_min'], nr['h_max']
                s_lo, s_hi = nr['s_min'], nr['s_max']
                v_lo, v_hi = nr['v_min'], nr['v_max']
            # Saturation floor: reject near-gray noise, but keep crosshair pixels
            s_lo = max(s_lo, 15)
            if h_lo > h_hi:
                bounds.append((
                    hr,
                    np.array([h_lo, s_lo, v_lo], dtype=np.uint8),
                    np.array([179, s_hi, v_hi], dtype=np.uint8),
                    np.array([0, s_lo, v_lo], dtype=np.uint8),
                    np.array([h_hi, s_hi, v_hi], dtype=np.uint8),
                ))
            else:
                bounds.append((
                    hr,
                    np.array([h_lo, s_lo, v_lo], dtype=np.uint8),
                    np.array([h_hi, s_hi, v_hi], dtype=np.uint8),
                    None, None,
                ))
        return bounds

    @staticmethod
    def _filter_contours(contours, min_area, max_area, is_small, roi_cx, roi_cy):
        valid = []
        # Crosshair is always near ROI center; reject contours in outer 30%
        max_cdist_sq = (roi_cx * 0.7) ** 2 + (roi_cy * 0.7) ** 2
        for cnt in contours:
            bx, by, bw, bh = cv2.boundingRect(cnt)
            rect_area = bw * bh
            if rect_area < min_area * 0.3 or rect_area > max_area * 2.0:
                continue
            if bh == 0:
                continue
            ar = float(bw) / bh
            if is_small:
                if ar < 0.15 or ar > 6.0:
                    continue
            elif ar < 0.3 or ar > 3.0:
                continue
            area = cv2.contourArea(cnt)
            if area < min_area or area > max_area:
                continue
            M = cv2.moments(cnt)
            if M['m00'] > 0:
                cX = M['m10'] / M['m00']
                cY = M['m01'] / M['m00']
            else:
                cX = bx + bw / 2.0
                cY = by + bh / 2.0
            dist_sq = (cX - roi_cx) ** 2 + (cY - roi_cy) ** 2
            if dist_sq > max_cdist_sq:
                continue
            valid.append((cnt, dist_sq, area, (bx, by, bw, bh), (cX, cY), 0.0))
        return valid

    @staticmethod
    def _merge_nearby(contours_data, merge_dist_sq, roi_cx, roi_cy):
        n = len(contours_data)
        parent = list(range(n))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        for i in range(n):
            ci = contours_data[i][4]
            for j in range(i + 1, n):
                cj = contours_data[j][4]
                if (ci[0] - cj[0]) ** 2 + (ci[1] - cj[1]) ** 2 < merge_dist_sq:
                    union(i, j)

        groups = {}
        for i in range(n):
            groups.setdefault(find(i), []).append(i)

        result = []
        for indices in groups.values():
            if len(indices) == 1:
                result.append(contours_data[indices[0]])
            else:
                total = sum(contours_data[i][2] for i in indices)
                if total < 0.001:
                    total = 0.001
                wcx = sum(contours_data[i][4][0] * contours_data[i][2] for i in indices) / total
                wcy = sum(contours_data[i][4][1] * contours_data[i][2] for i in indices) / total
                bx_min = min(contours_data[i][3][0] for i in indices)
                by_min = min(contours_data[i][3][1] for i in indices)
                bx_max = max(contours_data[i][3][0] + contours_data[i][3][2] for i in indices)
                by_max = max(contours_data[i][3][1] + contours_data[i][3][3] for i in indices)
                rect = (bx_min, by_min, bx_max - bx_min, by_max - by_min)
                ds = (wcx - roi_cx) ** 2 + (wcy - roi_cy) ** 2
                avg_s = sum(contours_data[i][5] for i in indices) / len(indices)
                result.append((contours_data[indices[0]][0], ds, total, rect, (wcx, wcy), avg_s))
        return result

    @staticmethod
    def _score_contours(valid, max_dist_sq, prev_target, roi_size):
        sticky_sq = 0.0
        if prev_target is not None:
            sticky_sq = (roi_size * 0.25) ** 2

        area_vals = [c[2] for c in valid]
        max_a = max(max(area_vals), 1.0)

        best_score = float('inf')
        best_idx = 0
        for idx, (cnt, dist_sq, area, rect, center, solidity) in enumerate(valid):
            score = (dist_sq / max_dist_sq) * 0.6 + (1.0 - area / max_a) * 0.25 + (1.0 - solidity) * 0.15
            if prev_target is not None:
                dp = (center[0] - prev_target[0]) ** 2 + (center[1] - prev_target[1]) ** 2
                if dp < sticky_sq:
                    # Proportional stickiness: closer to prev = stronger bonus
                    proximity = 1.0 - dp / sticky_sq
                    score *= max(0.25, 1.0 - proximity * 0.75)
            if score < best_score:
                best_score = score
                best_idx = idx
        return valid[best_idx]
