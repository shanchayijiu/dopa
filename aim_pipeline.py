import math
from math import sqrt as _sqrt
import random
import time
import threading

import numpy as np
from pid import DualAxisPID
from bytetrack import ByteTracker


class KalmanPredictor2D:
    """
    2D 恒速卡尔曼滤波预测器。
    维护 per-track_id 的滤波器状态，用于预测目标未来位置。
    状态向量: [x, y, vx, vy]
    """

    def __init__(self, process_noise=1.0, measurement_noise=5.0, max_tracks=64):
        self.process_noise = float(process_noise)
        self._measurement_noise = float(measurement_noise)
        self.max_tracks = int(max_tracks)
        self._tracks = {}  # track_id -> {x, P, last_time}
        # 预计算常量矩阵，避免每帧重建
        self._H = np.array([[1, 0, 0, 0], [0, 1, 0, 0]], dtype=np.float64)
        self._R = np.array([[self._measurement_noise, 0], [0, self._measurement_noise]], dtype=np.float64)
        self._I4 = np.eye(4, dtype=np.float64)
        self._F_template = np.eye(4, dtype=np.float64)
        self._Q_template = np.zeros((4, 4), dtype=np.float64)
        self._z_buf = np.empty(2, dtype=np.float64)
        self._P_init = np.diag([100.0, 100.0, 500.0, 500.0])

    @property
    def measurement_noise(self):
        return self._measurement_noise

    @measurement_noise.setter
    def measurement_noise(self, value):
        value = float(value)
        if value != self._measurement_noise:
            self._measurement_noise = value
            self._R = np.array([[value, 0], [0, value]], dtype=np.float64)

    def reset(self):
        self._tracks.clear()

    def _init_state(self, x, y):
        """初始化单个 track 的卡尔曼状态"""
        state = np.array([x, y, 0.0, 0.0], dtype=np.float64)
        P = self._P_init.copy()
        return state, P

    def _get_F(self, dt):
        """状态转移矩阵 (恒速模型) — 复用预分配模板"""
        F = self._F_template.copy()
        F[0, 2] = dt
        F[1, 3] = dt
        return F

    def _get_Q(self, dt):
        """过程噪声矩阵 — 复用预分配模板"""
        q = self.process_noise
        dt2 = dt * dt
        dt3 = dt2 * dt / 2.0
        dt4 = dt2 * dt2 / 4.0
        Q = self._Q_template.copy()
        Q[0, 0] = dt4; Q[0, 2] = dt3
        Q[1, 1] = dt4; Q[1, 3] = dt3
        Q[2, 0] = dt3; Q[2, 2] = dt2
        Q[3, 1] = dt3; Q[3, 3] = dt2
        Q *= q
        return Q

    def _get_H(self):
        """观测矩阵（预计算）"""
        return self._H

    def _get_R(self):
        """观测噪声矩阵（预计算）"""
        return self._R

    def update(self, track_id, mx, my):
        """
        用观测值更新指定 track 的卡尔曼状态。

        Args:
            track_id: 轨迹ID
            mx, my: 观测到的位置

        Returns:
            (filtered_x, filtered_y, vx, vy): 滤波后位置和速度估计
        """
        now = time.time()
        if track_id not in self._tracks:
            state, P = self._init_state(mx, my)
            self._tracks[track_id] = {'x': state, 'P': P, 'last_time': now}
            self._prune()
            return mx, my, 0.0, 0.0

        trk = self._tracks[track_id]
        dt = now - trk['last_time']
        if dt <= 0:
            dt = 0.008  # ~120fps fallback
        dt = min(dt, 0.5)  # 防止长时间丢失后 dt 过大

        x = trk['x']
        P = trk['P']

        # Predict
        F = self._get_F(dt)
        Q = self._get_Q(dt)
        x_pred = F @ x
        P_pred = F @ P @ F.T + Q

        # Update
        H = self._H
        R = self._R
        z = self._z_buf
        z[0] = mx; z[1] = my
        y_res = z - H @ x_pred
        S = H @ P_pred @ H.T + R
        try:
            K = P_pred @ H.T @ np.linalg.inv(S)
        except np.linalg.LinAlgError:
            K = np.zeros((4, 2), dtype=np.float64)

        x_new = x_pred + K @ y_res
        P_new = (self._I4 - K @ H) @ P_pred

        trk['x'] = x_new
        trk['P'] = P_new
        trk['last_time'] = now

        return float(x_new[0]), float(x_new[1]), float(x_new[2]), float(x_new[3])

    def predict(self, track_id, n_frames=1, frame_dt=None):
        """
        预测指定 track 未来 n_frames 帧的位置。

        Args:
            track_id: 轨迹ID
            n_frames: 预测帧数
            frame_dt: 每帧间隔秒数，None则自动估算

        Returns:
            (pred_x, pred_y) 或 None (track不存在时)
        """
        if track_id not in self._tracks:
            return None
        trk = self._tracks[track_id]
        x = trk['x']

        if frame_dt is None:
            frame_dt = 0.008  # ~120fps default

        total_dt = frame_dt * n_frames
        F = self._get_F(total_dt)
        x_pred = F @ x
        return float(x_pred[0]), float(x_pred[1])

    def remove(self, track_id):
        self._tracks.pop(track_id, None)

    def _prune(self):
        """超过 max_tracks 时清除最久未更新的"""
        if len(self._tracks) <= self.max_tracks:
            return
        items = sorted(self._tracks.items(), key=lambda kv: kv[1]['last_time'])
        remove_count = len(self._tracks) - self.max_tracks
        for i in range(remove_count):
            del self._tracks[items[i][0]]


class AimMoveQuantizer:
    def __init__(self):
        self._rx = 0.0
        self._ry = 0.0

    def reset(self):
        self._rx = 0.0
        self._ry = 0.0

    def quantize(self, dx, dy):
        try:
            x = float(dx) + float(self._rx)
            y = float(dy) + float(self._ry)
        except Exception:
            return dx, dy

        ix = int(x)
        iy = int(y)
        self._rx = x - ix
        self._ry = y - iy
        return ix, iy


class AimPointResolver:
    def __init__(self, default_randomize=True):
        self.default_randomize = bool(default_randomize)

    @staticmethod
    def _pick(a, b, randomize):
        try:
            a = float(a)
        except Exception:
            a = 0.5
        try:
            b = float(b)
        except Exception:
            b = 0.5
        low = min(a, b)
        high = max(a, b)
        if randomize and low != high:
            return random.uniform(low, high)
        return (low + high) * 0.5

    def resolve(self, pressed_key_config, class_id):
        randomize = bool(pressed_key_config.get('randomize_aim_position', self.default_randomize))

        if 'class_aim_positions' not in pressed_key_config:
            return self._pick(pressed_key_config.get('aim_bot_position', 0.5), pressed_key_config.get('aim_bot_position2', 0.5), randomize)
        class_str = str(class_id)
        if class_str in pressed_key_config['class_aim_positions']:
            cfg = pressed_key_config['class_aim_positions'][class_str]
            return self._pick(cfg.get('aim_bot_position', 0.5), cfg.get('aim_bot_position2', 0.5), randomize)
        return self._pick(pressed_key_config.get('aim_bot_position', 0.5), pressed_key_config.get('aim_bot_position2', 0.5), randomize)


class AimPipeline:
    def __init__(self):
        self._lock = threading.RLock()
        self._infer_lock = self._lock
        self._aim_lock = self._lock
        self.quantizer = AimMoveQuantizer()
        self.aim_point = AimPointResolver(default_randomize=True)
        self.pid = DualAxisPID(kp=[0.4, 0.4], ki=[0.02, 0.02], kd=[0.12, 0.12], windup_guard=[0.0, 0.0])
        self.target_history = {}
        self.last_target_count = 0
        self.last_target_count_by_class = {}
        self.target_switch_time_ms = 0.0
        self.is_waiting_for_switch = False
        self._cache = {
            'aim': {},
            'pid': {},
        }
        self._last_frame_id = None
        self._frame_seq = 0
        self._last_aim_boxes = None
        self._last_class_ids = None
        self._last_selected_target_id = None
        self._last_selected_target_pos = None
        self._last_output_target_id = None
        self._last_output_target_pos = None
        self._aim_position_cache = {}
        self._aim_position_cache_ttl_sec = 2.5
        self._last_prune_time = 0.0
        self._target_lock_time = 0.0
        # ByteTrack 跟踪器
        self.tracker = ByteTracker(track_thresh=0.5, match_thresh=0.3, track_buffer=30, max_center_dist=80.0)
        self.tracker_enabled = True
        # 卡尔曼预测器（保留但不用于位置替换）
        self.kalman = KalmanPredictor2D(process_noise=0.5, measurement_noise=15.0)
        self.kalman_enabled = True
        self.kalman_predict_frames = 5
        # 移动预测平滑状态
        self._lead_x = 0.0
        self._lead_y = 0.0
        self._lead_smooth = 0.18  # lead EMA 系数
        # 速度估计（用 PID 输出补偿屏幕速度）
        self._prev_aim_pos = None       # 上一帧目标屏幕坐标（原始，不含 lead）
        self._prev_aim_time = None      # 上一帧时间戳
        self._est_vx = 0.0  # 补偿后速度估计 (像素/秒)
        self._est_vy = 0.0
        self._vel_smooth = 0.25  # 速度 EMA 系数（提高灵敏度）
        self._vel_dir_count = 0  # 连续同向帧数
        self._prev_pid_raw = (0.0, 0.0)  # 上一帧原始 PID 输出（补偿观测速度用）
        self.predict_gain = 3.0  # PID输出→屏幕像素的估计系数
        # 目标ID强锁定
        self.target_id_lock_enabled = True
        self._locked_track_id = None
        self._locked_last_pos = None      # 锁定目标最后已知位置
        self._lock_grace_frames = 0       # 锁定目标消失后的宽限帧计数
        self._lock_grace_max = 20         # 最大宽限帧数（~300-600ms）

    def reset(self):
        with self._infer_lock:
            self._last_frame_id = None
            self._frame_seq = 0
            self._last_aim_boxes = None
            self._last_class_ids = None
        with self._aim_lock:
            self.quantizer.reset()
            self.pid.reset()
            self.reset_target_selection()
            self.tracker.reset()
            self.kalman.reset()
            self._locked_track_id = None
            self._locked_last_pos = None
            self._lock_grace_frames = 0
            self._lead_x = 0.0
            self._lead_y = 0.0
            self._prev_aim_pos = None
            self._prev_aim_time = None
            self._est_vx = 0.0
            self._est_vy = 0.0
            self._vel_dir_count = 0
            self._prev_pid_raw = (0.0, 0.0)
            self._cache['aim'].clear()
            self._cache['pid'].clear()

    def reset_target_selection(self):
        with self._aim_lock:
            self.target_history.clear()
            self.last_target_count = 0
            self.last_target_count_by_class.clear()
            self.target_switch_time_ms = 0.0
            self.is_waiting_for_switch = False
            self._last_selected_target_id = None
            self._last_selected_target_pos = None
            self._last_output_target_id = None
            self._last_output_target_pos = None
            self._aim_position_cache.clear()
            self._target_lock_time = 0.0
            self._locked_track_id = None
            self._locked_last_pos = None
            self._lock_grace_frames = 0

    def _prune_aim_position_cache(self):
        now = time.time()
        if now - self._last_prune_time < 1.0:
            return
        self._last_prune_time = now
        ttl = float(self._aim_position_cache_ttl_sec)
        for key in list(self._aim_position_cache.keys()):
            item = self._aim_position_cache.get(key)
            if not item:
                self._aim_position_cache.pop(key, None)
                continue
            if (now - float(item.get('ts', now))) > ttl:
                self._aim_position_cache.pop(key, None)

    def _resolve_aim_position_for_target(self, pressed_key_config, class_id, target_id, stable_random=True):
        if not stable_random or target_id is None:
            return self.aim_point.resolve(pressed_key_config, class_id)
        self._prune_aim_position_cache()
        cached = self._aim_position_cache.get(target_id)
        if cached is not None:
            cached['ts'] = time.time()
            return float(cached.get('val', 0.5))
        v = float(self.aim_point.resolve(pressed_key_config, class_id))
        self._aim_position_cache[target_id] = {'val': v, 'ts': time.time()}
        return v

    def _reset_pid_integral(self):
        self.pid._i_term['x'] = 0
        self.pid._i_term['y'] = 0

    def _coerce_boxes(self, boxes):
        if boxes is None:
            return None
        if isinstance(boxes, np.ndarray):
            arr = boxes
        else:
            try:
                arr = np.array(boxes, dtype=np.float32)
            except Exception:
                return None
        if arr.ndim != 2:
            return None
        if arr.shape[0] == 0:
            return None
        if arr.shape[1] < 4:
            return None
        if arr.dtype != np.float32:
            try:
                arr = arr.astype(np.float32, copy=False)
            except Exception:
                return None
        return arr[:, 0:4]

    def _coerce_class_ids(self, class_ids, n):
        if class_ids is None:
            return [0] * int(n)
        if not isinstance(class_ids, (list, tuple, np.ndarray)):
            return [0] * int(n)
        if isinstance(class_ids, np.ndarray):
            class_ids = class_ids.tolist()
        out = list(class_ids)
        if len(out) < n:
            out.extend([0] * (n - len(out)))
        elif len(out) > n:
            out = out[:n]
        return out

    def _normalize_frame_payload(self, frame_payload):
        if not isinstance(frame_payload, dict):
            return None
        boxes = self._coerce_boxes(frame_payload.get('boxes'))
        if boxes is None:
            return None
        n = int(boxes.shape[0])
        class_ids = self._coerce_class_ids(frame_payload.get('class_ids'), n)

        frame_id = frame_payload.get('frame_id')
        if frame_id is None:
            frame_id = id(boxes)

        try:
            input_w = float(frame_payload.get('input_w', 0.0) or 0.0)
        except Exception:
            input_w = 0.0
        try:
            input_h = float(frame_payload.get('input_h', 0.0) or 0.0)
        except Exception:
            input_h = 0.0

        return frame_id, boxes, class_ids, input_w, input_h

    def _get_aim_params(self, cfg, pressed_key_config):
        c = self._cache['aim']
        ste = cfg.get('small_target_enhancement', {})
        if not isinstance(ste, dict):
            ste = {}
        ste_enabled = bool(ste.get('enabled', False))
        ste_smooth = bool(ste.get('smooth_enabled', False))
        try:
            smooth_frames = int(ste.get('smooth_frames', 5))
        except Exception:
            smooth_frames = 5
        smooth_frames = max(2, min(12, smooth_frames))
        try:
            small_threshold = float(ste.get('threshold', 0.01))
        except Exception:
            small_threshold = 0.01
        try:
            medium_threshold = float(ste.get('medium_threshold', 0.05))
        except Exception:
            medium_threshold = 0.05
        try:
            small_boost = float(ste.get('boost_factor', 2.0))
        except Exception:
            small_boost = 2.0
        try:
            medium_boost = float(ste.get('medium_boost', 1.5))
        except Exception:
            medium_boost = 1.5
        try:
            min_position_offset = float(pressed_key_config.get('min_position_offset', 0.0))
        except Exception:
            min_position_offset = 0.0
        try:
            move_deadzone = float(pressed_key_config.get('move_deadzone', 1.0))
        except Exception:
            move_deadzone = 1.0
        try:
            target_switch_delay = float(pressed_key_config.get('target_switch_delay', 0))
        except Exception:
            target_switch_delay = 0.0
        target_switch_delay = max(0.0, target_switch_delay)
        try:
            reference_class = int(pressed_key_config.get('target_reference_class', 0))
        except Exception:
            reference_class = 0
        try:
            target_sticky_pixels = float(cfg.get('target_sticky_pixels', 40.0))
        except Exception:
            target_sticky_pixels = 40.0
        try:
            target_lock_ms = float(cfg.get('target_lock_ms', 150.0))
        except Exception:
            target_lock_ms = 150.0
        target_lock_ms = max(0.0, min(1000.0, target_lock_ms))
        try:
            large_target_threshold = float(cfg.get('large_target_threshold', 0.055))
        except Exception:
            large_target_threshold = 0.055
        try:
            large_target_boost = float(cfg.get('large_target_boost', 1.12))
        except Exception:
            large_target_boost = 1.12

        # 卡尔曼预测参数
        kalman_cfg = cfg.get('kalman', {})
        if not isinstance(kalman_cfg, dict):
            kalman_cfg = {}
        kalman_enabled = bool(kalman_cfg.get('enabled', True))
        try:
            kalman_predict_frames = int(kalman_cfg.get('predict_frames', 5))
        except Exception:
            kalman_predict_frames = 5
        kalman_predict_frames = max(0, min(20, kalman_predict_frames))
        try:
            kalman_process_noise = float(kalman_cfg.get('process_noise', 0.5))
        except Exception:
            kalman_process_noise = 0.5
        try:
            kalman_measurement_noise = float(kalman_cfg.get('measurement_noise', 15.0))
        except Exception:
            kalman_measurement_noise = 15.0
        try:
            predict_gain = float(kalman_cfg.get('predict_gain', 3.0))
        except Exception:
            predict_gain = 3.0
        predict_gain = max(0.0, min(20.0, predict_gain))

        # 目标ID强锁定
        target_id_lock_enabled = bool(cfg.get('target_id_lock_enabled', True))

        key = (
            ste_enabled,
            ste_smooth,
            smooth_frames,
            small_threshold,
            medium_threshold,
            small_boost,
            medium_boost,
            min_position_offset,
            move_deadzone,
            target_switch_delay,
            reference_class,
            target_sticky_pixels,
            target_lock_ms,
            large_target_threshold,
            large_target_boost,
            bool(cfg.get('auto_flashbang', {}).get('enabled')) if isinstance(cfg.get('auto_flashbang', {}), dict) else False,
            kalman_enabled,
            kalman_predict_frames,
            kalman_process_noise,
            kalman_measurement_noise,
            predict_gain,
            target_id_lock_enabled,
        )
        if c.get('key') != key:
            c['key'] = key
            c['ste_enabled'] = ste_enabled
            c['ste_smooth'] = ste_smooth
            c['smooth_frames'] = smooth_frames
            c['small_threshold'] = small_threshold
            c['medium_threshold'] = medium_threshold
            c['small_boost'] = small_boost
            c['medium_boost'] = medium_boost
            c['min_position_offset'] = min_position_offset
            c['move_deadzone'] = move_deadzone
            c['target_switch_delay'] = target_switch_delay
            c['reference_class'] = reference_class
            c['target_sticky_pixels'] = target_sticky_pixels
            c['target_lock_ms'] = target_lock_ms
            c['large_target_threshold'] = large_target_threshold
            c['large_target_boost'] = large_target_boost
            c['auto_flashbang'] = key[15]
            c['kalman_enabled'] = kalman_enabled
            c['kalman_predict_frames'] = kalman_predict_frames
            c['kalman_process_noise'] = kalman_process_noise
            c['kalman_measurement_noise'] = kalman_measurement_noise
            c['predict_gain'] = predict_gain
            c['target_id_lock_enabled'] = target_id_lock_enabled
            # 同步卡尔曼参数到预测器
            self.kalman_enabled = kalman_enabled
            self.kalman_predict_frames = kalman_predict_frames
            self.predict_gain = predict_gain
            if abs(self.kalman.process_noise - kalman_process_noise) > 1e-6 or \
               abs(self.kalman.measurement_noise - kalman_measurement_noise) > 1e-6:
                self.kalman.process_noise = kalman_process_noise
                self.kalman.measurement_noise = kalman_measurement_noise
            self.target_id_lock_enabled = target_id_lock_enabled
        return c

    def _get_pid_params(self, pressed_key_config):
        c = self._cache['pid']
        try:
            move_deadzone = float(pressed_key_config.get('move_deadzone', 1.0))
        except Exception:
            move_deadzone = 1.0
        key = (move_deadzone,)
        if c.get('key') != key:
            c['key'] = key
            c['move_deadzone'] = move_deadzone
        return c

    def smooth_small_targets(self, targets, aim_params):
        if (not aim_params.get('ste_enabled')) or (not aim_params.get('ste_smooth')):
            return targets

        current_t = time.time()
        max_frames = int(aim_params.get('smooth_frames', 5))

        for target_id in list(self.target_history.keys()):
            history = self.target_history[target_id]
            frames = history.get('frames', [])
            frames = [f for f in frames if (current_t - float(f.get('time', current_t))) < 1.0]
            if len(frames) > max_frames:
                frames = frames[-max_frames:]
            if frames:
                history['frames'] = frames
            else:
                del self.target_history[target_id]

        smoothed_targets = []
        small_threshold = float(aim_params.get('small_threshold', 0.01))

        for target in targets:
            target_id = target.get('id')
            relative_size = float(target.get('relative_size', 0.0) or 0.0)
            if relative_size < small_threshold and target_id:
                if target_id not in self.target_history:
                    self.target_history[target_id] = {'frames': []}
                frame_info = {
                    'time': current_t,
                    'pos': target['pos'],
                    'size': target.get('size', 0.0),
                }
                self.target_history[target_id]['frames'].append(frame_info)
                frames = self.target_history[target_id]['frames']
                if len(frames) > max_frames:
                    frames = frames[-max_frames:]
                    self.target_history[target_id]['frames'] = frames
                if len(frames) >= 2:
                    avg_x = sum((f['pos'][0] for f in frames)) / len(frames)
                    avg_y = sum((f['pos'][1] for f in frames)) / len(frames)
                    avg_size = sum((float(f.get('size', 0.0)) for f in frames)) / len(frames)
                    t2 = target.copy()
                    t2['pos'] = (avg_x, avg_y)
                    t2['size'] = avg_size
                    smoothed_targets.append(t2)
                else:
                    smoothed_targets.append(target)
            else:
                smoothed_targets.append(target)

        return smoothed_targets

    def select_target_by_priority(self, targets, aim_scope, center_xy, aim_params):
        target_id_lock = bool(aim_params.get('target_id_lock_enabled', False))

        if not targets:
            if self.last_target_count > 0:
                self.last_target_count = 0
                self.last_target_count_by_class.clear()
                self._reset_pid_integral()
            self._last_selected_target_id = None
            self._last_selected_target_pos = None
            # 无目标时，若有锁定目标则消耗宽限帧而非立即释放
            if target_id_lock and self._locked_track_id is not None:
                self._lock_grace_frames += 1
                if self._lock_grace_frames > self._lock_grace_max:
                    self._locked_track_id = None
                    self._locked_last_pos = None
                    self._lock_grace_frames = 0
            return None

        try:
            aim_scope = float(aim_scope)
        except Exception:
            aim_scope = 0.0
        if aim_scope <= 0:
            aim_scope = float('inf')

        center_x, center_y = center_xy
        valid_targets = []
        for target in targets:
            dx = float(target['pos'][0]) - float(center_x)
            dy = float(target['pos'][1]) - float(center_y)
            dist = _sqrt(dx * dx + dy * dy)
            if dist <= aim_scope:
                target['distance_to_center'] = dist
                valid_targets.append(target)

        if not valid_targets:
            if self.last_target_count > 0:
                self.last_target_count = 0
                self.last_target_count_by_class.clear()
                self._reset_pid_integral()
            self._last_selected_target_id = None
            self._last_selected_target_pos = None
            # 有效目标为空时消耗宽限帧
            if target_id_lock and self._locked_track_id is not None:
                self._lock_grace_frames += 1
                if self._lock_grace_frames > self._lock_grace_max:
                    self._locked_track_id = None
                    self._locked_last_pos = None
                    self._lock_grace_frames = 0
            return None

        target_switch_delay = float(aim_params.get('target_switch_delay', 0.0))
        reference_class = int(aim_params.get('reference_class', 0))

        current_total_count = len(valid_targets)
        prev_total_count = int(self.last_target_count)
        current_ref_count = sum(1 for t in valid_targets if int(t.get('class_id', 0) or 0) == reference_class)

        if target_switch_delay > 0 and (not self.is_waiting_for_switch) and (prev_total_count > 1) and (current_total_count < prev_total_count):
            self.is_waiting_for_switch = True
            self.target_switch_time_ms = time.time() * 1000.0
            self._reset_pid_integral()
            return None

        if self.is_waiting_for_switch and current_total_count > prev_total_count:
            self.is_waiting_for_switch = False

        if target_switch_delay == 0 and current_total_count < prev_total_count and prev_total_count > 0:
            self._reset_pid_integral()

        if self.is_waiting_for_switch:
            now_ms = time.time() * 1000.0
            if (now_ms - float(self.target_switch_time_ms)) >= target_switch_delay:
                self.is_waiting_for_switch = False
            else:
                return None

        self.last_target_count_by_class[reference_class] = current_ref_count
        self.last_target_count = current_total_count

        # ---- 目标ID强锁定：track_id 存在于有效目标中则始终保持 ----
        if target_id_lock and self._locked_track_id is not None:
            locked_target = None
            for t in valid_targets:
                if t.get('track_id') == self._locked_track_id or t.get('id') == self._locked_track_id:
                    locked_target = t
                    break
            # track_id 未匹配时，尝试位置兜底重关联
            # （ByteTracker 可能给同一物理目标分配了新 track_id）
            if locked_target is None and self._locked_last_pos is not None:
                lx, ly = self._locked_last_pos
                best_d = 1e9
                best_t = None
                for t in valid_targets:
                    dx = float(t['pos'][0]) - lx
                    dy = float(t['pos'][1]) - ly
                    d = dx * dx + dy * dy
                    if d < best_d:
                        best_d = d
                        best_t = t
                # 距离阈值：上一位置 40px 以内视为同一目标
                if best_t is not None and best_d < 40.0 * 40.0:
                    locked_target = best_t
                    self._locked_track_id = best_t.get('track_id', best_t.get('id'))

            if locked_target is not None:
                # 锁定目标仍存在，重置宽限计数
                self._lock_grace_frames = 0
                self._last_selected_target_id = locked_target.get('id')
                self._last_selected_target_pos = locked_target.get('pos')
                self._locked_last_pos = locked_target.get('pos')
                self.last_target_count = current_total_count
                return locked_target
            else:
                # 锁定目标不在当前帧，消耗宽限帧
                self._lock_grace_frames += 1
                if self._lock_grace_frames <= self._lock_grace_max:
                    # 宽限期内：不选新目标，等待锁定目标回来
                    self.last_target_count = current_total_count
                    return None
                else:
                    # 宽限期结束：释放锁定，允许选择新目标
                    self._locked_track_id = None
                    self._locked_last_pos = None
                    self._lock_grace_frames = 0
                    self._reset_pid_integral()

        # ---- 目标锁定冷却：选中目标后一段时间内不切换 ----
        lock_ms = float(aim_params.get('target_lock_ms', 150.0))
        sticky_margin = float(aim_params.get('target_sticky_pixels', 40.0))
        if lock_ms > 0 and self._last_selected_target_id is not None:
            elapsed = time.time() * 1000.0 - self._target_lock_time
            if elapsed < lock_ms:
                locked = self._find_locked_target(valid_targets, sticky_margin)
                if locked is not None:
                    self._last_selected_target_pos = locked.get('pos')
                    return locked

        valid_targets.sort(key=lambda x: (float(x.get('distance_to_center', 1e9)), -float(x.get('size', 0.0) or 0.0)))
        selected = valid_targets[0]

        # ---- 粘滞：已选目标在迟滞范围内则保持 ----
        sticky_id = self._last_selected_target_id
        large_threshold = float(aim_params.get('large_target_threshold', 0.055))
        sticky_target = None
        if sticky_id is not None:
            for t in valid_targets:
                if t.get('id') == sticky_id:
                    sticky_target = t
                    break

        if sticky_target is None and self._last_selected_target_pos is not None:
            lx, ly = self._last_selected_target_pos
            best_last_dist = 1e9
            for t in valid_targets:
                dx = float(t['pos'][0]) - float(lx)
                dy = float(t['pos'][1]) - float(ly)
                d = _sqrt(dx * dx + dy * dy)
                if d < best_last_dist:
                    best_last_dist = d
                    sticky_target = t
            if sticky_target is not None:
                threshold = sticky_margin * 1.35
                if float(sticky_target.get('relative_size', 0.0) or 0.0) >= large_threshold:
                    threshold += 16.0
                if best_last_dist > threshold:
                    sticky_target = None

        if sticky_target is not None:
            effective_margin = sticky_margin
            if float(sticky_target.get('relative_size', 0.0) or 0.0) >= large_threshold:
                effective_margin += 12.0
            if float(sticky_target.get('distance_to_center', 1e9)) <= float(selected.get('distance_to_center', 1e9)) + effective_margin:
                selected = sticky_target

        # 目标切换时重置锁定计时
        if selected.get('id') != self._last_selected_target_id:
            self._target_lock_time = time.time() * 1000.0
            self._reset_pid_integral()

        self._last_selected_target_id = selected.get('id')
        self._last_selected_target_pos = selected.get('pos')
        # 更新强锁定 track_id
        if target_id_lock:
            self._locked_track_id = selected.get('track_id', selected.get('id'))
            self._locked_last_pos = selected.get('pos')
        return selected

    def _find_locked_target(self, valid_targets, sticky_margin):
        """在有效目标中查找已锁定的目标（按ID优先，位置兜底）"""
        locked_id = self._last_selected_target_id
        for t in valid_targets:
            if t.get('id') == locked_id:
                return t
        if self._last_selected_target_pos is not None:
            lx, ly = self._last_selected_target_pos
            best_d = 1e9
            best_t = None
            for t in valid_targets:
                dx = float(t['pos'][0]) - float(lx)
                dy = float(t['pos'][1]) - float(ly)
                d = _sqrt(dx * dx + dy * dy)
                if d < best_d:
                    best_d = d
                    best_t = t
            if best_t is not None and best_d < sticky_margin:
                self._last_selected_target_id = best_t.get('id')
                return best_t
        return None

    def select_from_aim_targets(self, aim_targets, class_ids, identify_left, identify_top, pressed_key_config, cfg, aim_scope, center_xy, model_area):
        with self._aim_lock:
            if aim_targets is None or len(aim_targets) == 0:
                # 无检测时也要通知 tracker（让轨迹进入 lost）
                if self.tracker_enabled:
                    self.tracker.update(None)
                return None

            try:
                model_area = float(model_area)
            except Exception:
                model_area = 102400.0
            if model_area <= 0:
                model_area = 102400.0

            c = self._get_aim_params(cfg, pressed_key_config)
            ste_enabled = bool(c.get('ste_enabled', False))
            small_threshold = float(c.get('small_threshold', 0.01))
            medium_threshold = float(c.get('medium_threshold', 0.05))
            small_boost = float(c.get('small_boost', 2.0))
            medium_boost = float(c.get('medium_boost', 1.5))
            large_target_threshold = float(c.get('large_target_threshold', 0.055))
            large_target_boost = float(c.get('large_target_boost', 1.12))
            min_position_offset = float(c.get('min_position_offset', 0.0))

            # ---- 构建检测框列表（屏幕坐标系 x1,y1,x2,y2）用于 tracker ----
            det_boxes = []
            det_scores = []
            det_class_ids = []
            det_meta = []  # 保存每个检测的元信息
            _id_left = float(identify_left)
            _id_top = float(identify_top)
            for i in range(len(aim_targets)):
                item = aim_targets[i]
                result_center_x, result_center_y, width, height = item
                class_id = class_ids[i] if i < len(class_ids) else 0

                aim_position = self._resolve_aim_position_for_target(
                    pressed_key_config=pressed_key_config,
                    class_id=class_id,
                    target_id=None,
                    stable_random=False,
                )
                absolute_area = float(width) * float(height)
                relative_size = absolute_area / model_area

                size_boost = 1.0
                if ste_enabled:
                    if relative_size < small_threshold:
                        size_boost = small_boost
                    elif relative_size < medium_threshold:
                        size_boost = medium_boost
                if relative_size >= large_target_threshold:
                    size_boost *= large_target_boost
                final_size_score = relative_size * size_boost

                f_cx = float(result_center_x)
                f_cy = float(result_center_y)
                f_w = float(width)
                f_h = float(height)
                px = _id_left + f_cx
                py = _id_top + (f_cy - f_h * 0.5) + max(f_h * float(aim_position), float(min_position_offset))

                # 屏幕坐标系下的检测框
                sx1 = _id_left + f_cx - f_w * 0.5
                sy1 = _id_top + f_cy - f_h * 0.5
                sx2 = sx1 + f_w
                sy2 = sy1 + f_h
                det_boxes.append([sx1, sy1, sx2, sy2])
                det_scores.append(1.0)  # YOLO 后已过滤, 此处统一给 1.0
                det_class_ids.append(class_id)
                det_meta.append({
                    'pos': (px, py),
                    'size': final_size_score,
                    'absolute_size': absolute_area,
                    'relative_size': relative_size,
                    'class_id': class_id,
                    'aim_position': aim_position,
                    'box_w': f_w,
                    'box_h': f_h,
                })

            # ---- 通过 ByteTracker 获取稳定 track_id ----
            if self.tracker_enabled and len(det_boxes) > 0:
                tracks = self.tracker.update(
                    np.array(det_boxes, dtype=np.float32),
                    np.array(det_scores, dtype=np.float32),
                    np.array(det_class_ids, dtype=np.int32),
                )
                # 将 track 与最近的 det_meta 关联（贪心去重）
                targets = []
                used_det = set()
                # 按置信度排序优先分配
                for trk in tracks:
                    tc = trk.center
                    best_idx = None
                    best_dist = 1e9
                    for j, meta in enumerate(det_meta):
                        if j in used_det:
                            continue
                        box_cx = (det_boxes[j][0] + det_boxes[j][2]) * 0.5
                        box_cy = (det_boxes[j][1] + det_boxes[j][3]) * 0.5
                        dx = tc[0] - box_cx
                        dy = tc[1] - box_cy
                        d = dx * dx + dy * dy
                        if d < best_dist:
                            best_dist = d
                            best_idx = j
                    if best_idx is not None:
                        used_det.add(best_idx)
                        meta = det_meta[best_idx]
                        # 用 track_id 做 stable_random，保证同一 track 瞄准点不跳动
                        stable_aim_pos = self._resolve_aim_position_for_target(
                            pressed_key_config=pressed_key_config,
                            class_id=meta['class_id'],
                            target_id=trk.track_id,
                            stable_random=True,
                        )
                        # 用稳定的 aim_position 重算瞄准点
                        box_top_y = det_boxes[best_idx][1]
                        box_h = meta['box_h']
                        stable_py = box_top_y + max(float(box_h) * float(stable_aim_pos), float(min_position_offset))
                        stable_px = (det_boxes[best_idx][0] + det_boxes[best_idx][2]) * 0.5
                        t = dict(meta)
                        t['pos'] = (stable_px, stable_py)
                        t['aim_position'] = stable_aim_pos
                        t['id'] = trk.track_id
                        t['track_id'] = trk.track_id
                        t['velocity'] = trk.velocity.tolist()
                        targets.append(t)
            else:
                # tracker 未启用时退回位置 ID
                targets = []
                for j, meta in enumerate(det_meta):
                    t = dict(meta)
                    t['id'] = f"{int(meta['pos'][0])}_{int(meta['pos'][1])}"
                    targets.append(t)

            if bool(c.get('auto_flashbang', False)):
                targets = [t for t in targets if int(t.get('class_id', -1)) != 4]

            targets = self.smooth_small_targets(targets, c)
            return self.select_target_by_priority(targets, aim_scope, center_xy, c)

    def step_aim(self, aim_targets, class_ids, identify_left, identify_top, pressed_key_config, cfg, aim_scope, center_xy, model_area, auto_y=False, left_pressed_long=False):
        with self._aim_lock:
            nearest = self.select_from_aim_targets(
                aim_targets=aim_targets,
                class_ids=class_ids,
                identify_left=identify_left,
                identify_top=identify_top,
                pressed_key_config=pressed_key_config,
                cfg=cfg,
                aim_scope=aim_scope,
                center_xy=center_xy,
                model_area=model_area,
            )
            if nearest is None:
                # During lock grace period, hold position instead of full reset
                if self._locked_track_id is not None and self._lock_grace_frames > 0:
                    return (0.0, 0.0)
                self._last_output_target_id = None
                self._last_output_target_pos = None
                self._prev_aim_pos = None
                self._prev_aim_time = None
                self._est_vx = 0.0
                self._est_vy = 0.0
                self._lead_x = 0.0
                self._lead_y = 0.0
                self._vel_dir_count = 0
                self._prev_pid_raw = (0.0, 0.0)
                return None
            target_id = nearest.get('id')
            aim_x = float(nearest['pos'][0])
            aim_y = float(nearest['pos'][1])

            # 目标切换时重置速度估计
            if target_id != self._last_output_target_id and self._last_output_target_id is not None:
                self._prev_aim_pos = None
                self._prev_aim_time = None
                self._est_vx = 0.0
                self._est_vy = 0.0
                self._lead_x = 0.0
                self._lead_y = 0.0
                self._vel_dir_count = 0
                self._prev_pid_raw = (0.0, 0.0)

            # ---- 移动预测：PID输出补偿 + 预测位置喂给 PID ----
            # 问题：PID 跟踪会抵消目标的屏幕速度，导致观测速度≈0
            # 方案：用上一帧 PID 输出（=我们移动鼠标的量）补偿观测速度
            #       true_vel ≈ obs_vel + prev_pid_output × predict_gain
            now = time.time()
            if self.kalman_enabled and self.kalman_predict_frames > 0:
                if self._prev_aim_pos is not None and self._prev_aim_time is not None:
                    dt = now - self._prev_aim_time
                    if 0.001 < dt < 0.5:
                        obs_dx = aim_x - self._prev_aim_pos[0]
                        obs_dy = aim_y - self._prev_aim_pos[1]
                        # 用 PID 输出补偿：屏幕移动了 prev_pid * gain 像素
                        comp_dx = obs_dx + self._prev_pid_raw[0] * self.predict_gain
                        comp_dy = obs_dy + self._prev_pid_raw[1] * self.predict_gain
                        raw_vx = comp_dx / dt
                        raw_vy = comp_dy / dt
                        max_vel = 2000.0
                        raw_vx = max(-max_vel, min(max_vel, raw_vx))
                        raw_vy = max(-max_vel, min(max_vel, raw_vy))
                        va = self._vel_smooth
                        self._est_vx = va * raw_vx + (1.0 - va) * self._est_vx
                        self._est_vy = va * raw_vy + (1.0 - va) * self._est_vy
                        if (raw_vx * self._est_vx + raw_vy * self._est_vy) > 0:
                            self._vel_dir_count = min(self._vel_dir_count + 1, 30)
                        else:
                            self._vel_dir_count = max(self._vel_dir_count - 2, 0)

                vel_mag = math.sqrt(self._est_vx * self._est_vx + self._est_vy * self._est_vy)
                if vel_mag > 60.0 and self._vel_dir_count >= 3:
                    lead_time = float(self.kalman_predict_frames) * 0.008
                    raw_lx = self._est_vx * lead_time
                    raw_ly = self._est_vy * lead_time
                    lead_mag = math.sqrt(raw_lx * raw_lx + raw_ly * raw_ly)
                    max_lead = 40.0
                    if lead_mag > max_lead:
                        s = max_lead / lead_mag
                        raw_lx *= s
                        raw_ly *= s
                    la = self._lead_smooth
                    self._lead_x = la * raw_lx + (1.0 - la) * self._lead_x
                    self._lead_y = la * raw_ly + (1.0 - la) * self._lead_y
                else:
                    self._lead_x *= 0.5
                    self._lead_y *= 0.5

                aim_x += self._lead_x
                aim_y += self._lead_y
                self._prev_aim_pos = (aim_x - self._lead_x, aim_y - self._lead_y)
                self._prev_aim_time = now

            nearest['pos'] = (aim_x, aim_y)
            self._last_output_target_id = target_id
            self._last_output_target_pos = (aim_x, aim_y)
            cx, cy = center_xy
            error_x = aim_x - float(cx)
            error_y = aim_y - float(cy)
            pid_result = self._compute_pid_move_locked(error_x, error_y, pressed_key_config, auto_y=auto_y, left_pressed_long=left_pressed_long)
            return pid_result

    def step_frame(self, frame_payload, pressed_key_config, cfg, center_xy, aim_scope, identify_left, identify_top, model_area, auto_y=False, left_pressed_long=False, debug=False):
        with self._aim_lock:
            normalized = self._normalize_frame_payload(frame_payload)
            if normalized is None:
                return None
            frame_id, boxes, class_ids, input_w, input_h = normalized

            if frame_id != self._last_frame_id:
                self._last_frame_id = frame_id
                self._frame_seq += 1
                self._last_class_ids = class_ids
                self._last_aim_boxes = boxes

            candidates = self._last_aim_boxes if self._last_aim_boxes is not None else boxes
            cand_class_ids = self._last_class_ids if self._last_class_ids is not None else class_ids

            return self.step_aim(
                aim_targets=candidates,
                class_ids=cand_class_ids,
                identify_left=identify_left,
                identify_top=identify_top,
                pressed_key_config=pressed_key_config,
                cfg=cfg,
                aim_scope=aim_scope,
                center_xy=center_xy,
                model_area=model_area,
                auto_y=auto_y,
                left_pressed_long=left_pressed_long,
            )

    def _compute_pid_move_locked(self, error_x, error_y, pressed_key_config, auto_y=False, left_pressed_long=False):
        """PID计算 + 量化移动量（内部方法，调用时已持有锁）"""
        relative_move_x, relative_move_y = self.pid.compute(error_x, error_y)
        self._prev_pid_raw = (relative_move_x, relative_move_y)
        if auto_y and left_pressed_long:
            relative_move_y = 0
        move_threshold = float(pressed_key_config.get('move_deadzone', 1.0))
        if abs(relative_move_x) > move_threshold or abs(relative_move_y) > move_threshold:
            return self.quantizer.quantize(relative_move_x, relative_move_y)
        return None

    def compute_pid_move(self, error_x, error_y, pressed_key_config, auto_y=False, left_pressed_long=False):
        """PID计算 + 量化移动量（外部调用，自动加锁）"""
        with self._aim_lock:
            return self._compute_pid_move_locked(error_x, error_y, pressed_key_config, auto_y=auto_y, left_pressed_long=left_pressed_long)
