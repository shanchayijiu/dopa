"""
ByteTrack 轻量级多目标跟踪器

基于 ByteTrack 论文思想，使用 IoU 匹配 + 匈牙利算法实现帧间目标关联。
设计为嵌入 AimPipeline 使用，提供稳定的 track_id 用于目标锁定。

依赖: scipy.optimize.linear_sum_assignment (匈牙利算法)
"""

import time
import numpy as np
from scipy.optimize import linear_sum_assignment


class STrack:
    """单目标跟踪轨迹"""

    _next_id = 1

    class State:
        NEW = 0
        TRACKED = 1
        LOST = 2
        REMOVED = 3

    def __init__(self, bbox, score, class_id):
        """
        Args:
            bbox: [x1, y1, x2, y2] 检测框
            score: 置信度
            class_id: 类别ID
        """
        self.track_id = 0  # 分配后赋值
        self.bbox = np.array(bbox, dtype=np.float32)
        self.score = float(score)
        self.class_id = int(class_id)
        self.state = self.State.NEW
        self.is_activated = False
        self.frame_id = 0
        self.start_frame = 0
        self.tracklet_len = 0
        # EMA 平滑速度估计 (像素/帧)
        self._velocity = np.zeros(2, dtype=np.float32)
        self._vel_alpha = 0.15  # EMA 平滑系数，越小越平滑
        self._center_cache = None  # 缓存 center 计算结果

    @staticmethod
    def reset_id():
        STrack._next_id = 1

    @staticmethod
    def next_id():
        tid = STrack._next_id
        STrack._next_id += 1
        return tid

    @property
    def center(self):
        if self._center_cache is None:
            self._center_cache = np.array([
                (self.bbox[0] + self.bbox[2]) * 0.5,
                (self.bbox[1] + self.bbox[3]) * 0.5,
            ], dtype=np.float32)
        return self._center_cache

    @property
    def wh(self):
        return np.array([
            self.bbox[2] - self.bbox[0],
            self.bbox[3] - self.bbox[1],
        ], dtype=np.float32)

    @property
    def velocity(self):
        """返回 (vx, vy) 像素/帧"""
        return self._velocity.copy()

    def predict(self):
        """用匀速模型预测下一帧位置"""
        cx, cy = self.center
        w, h = self.wh
        cx += self._velocity[0]
        cy += self._velocity[1]
        self.bbox = np.array([
            cx - w * 0.5, cy - h * 0.5,
            cx + w * 0.5, cy + h * 0.5,
        ], dtype=np.float32)
        self._center_cache = None

    def activate(self, frame_id):
        """激活新轨迹"""
        self.track_id = self.next_id()
        self.state = self.State.TRACKED
        self.is_activated = True
        self.frame_id = frame_id
        self.start_frame = frame_id
        self.tracklet_len = 0

    def re_activate(self, new_det, frame_id):
        """重新激活丢失的轨迹"""
        old_center = self.center.copy()
        self.bbox = np.array(new_det.bbox, dtype=np.float32)
        self._center_cache = None
        self.score = new_det.score
        self.class_id = new_det.class_id
        new_center = self.center
        # 丢失后重新激活，用新速度重置（不做EMA，因为旧速度已过时）
        self._velocity = new_center - old_center
        self.state = self.State.TRACKED
        self.is_activated = True
        self.frame_id = frame_id
        self.tracklet_len = 0

    def update(self, new_det, frame_id):
        """用新检测更新轨迹"""
        old_center = self.center.copy()
        self.bbox = np.array(new_det.bbox, dtype=np.float32)
        self._center_cache = None
        self.score = new_det.score
        self.class_id = new_det.class_id
        new_center = self.center
        raw_vel = new_center - old_center
        # EMA 平滑速度，减少检测抖动导致的预测偏移
        self._velocity = self._vel_alpha * raw_vel + (1.0 - self._vel_alpha) * self._velocity
        self.state = self.State.TRACKED
        self.is_activated = True
        self.frame_id = frame_id
        self.tracklet_len += 1

    def mark_lost(self):
        self.state = self.State.LOST

    def mark_removed(self):
        self.state = self.State.REMOVED


def _iou_batch(bboxes_a, bboxes_b):
    """
    计算两组框的 IoU 矩阵

    Args:
        bboxes_a: (N, 4) [x1,y1,x2,y2]
        bboxes_b: (M, 4) [x1,y1,x2,y2]

    Returns:
        (N, M) IoU矩阵
    """
    a = np.array(bboxes_a, dtype=np.float32)
    b = np.array(bboxes_b, dtype=np.float32)
    if a.ndim == 1:
        a = a.reshape(1, -1)
    if b.ndim == 1:
        b = b.reshape(1, -1)
    if len(a) == 0 or len(b) == 0:
        return np.zeros((len(a), len(b)), dtype=np.float32)

    # 交集
    inter_x1 = np.maximum(a[:, 0:1], b[:, 0:1].T)
    inter_y1 = np.maximum(a[:, 1:2], b[:, 1:2].T)
    inter_x2 = np.minimum(a[:, 2:3], b[:, 2:3].T)
    inter_y2 = np.minimum(a[:, 3:4], b[:, 3:4].T)
    inter_area = np.maximum(0, inter_x2 - inter_x1) * np.maximum(0, inter_y2 - inter_y1)

    # 各自面积
    area_a = (a[:, 2] - a[:, 0]) * (a[:, 3] - a[:, 1])
    area_b = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])

    union = area_a[:, None] + area_b[None, :] - inter_area
    iou = np.where(union > 0, inter_area / union, 0.0)
    return iou.astype(np.float32)


def _linear_assignment(cost_matrix, thresh):
    """
    匈牙利算法匹配，复用 scipy.optimize.linear_sum_assignment

    Args:
        cost_matrix: (N, M) 代价矩阵 (值越小越匹配)
        thresh: 最大接受代价阈值

    Returns:
        matches: [(row, col), ...]
        unmatched_rows: [int, ...]
        unmatched_cols: [int, ...]
    """
    if cost_matrix.size == 0:
        return [], list(range(cost_matrix.shape[0])), list(range(cost_matrix.shape[1]))

    row_indices, col_indices = linear_sum_assignment(cost_matrix)

    matches = []
    matched_rows = set()
    matched_cols = set()

    for r, c in zip(row_indices, col_indices):
        if cost_matrix[r, c] <= thresh:
            matches.append((r, c))
            matched_rows.add(r)
            matched_cols.add(c)

    unmatched_rows = [i for i in range(cost_matrix.shape[0]) if i not in matched_rows]
    unmatched_cols = [j for j in range(cost_matrix.shape[1]) if j not in matched_cols]

    return matches, unmatched_rows, unmatched_cols


class ByteTracker:
    """
    ByteTrack 跟踪器

    参数:
        track_thresh: 高/低分检测分界阈值 (默认 0.5)
        match_thresh: IoU匹配阈值，越大越宽松 (默认 0.3)
        track_buffer: 丢失轨迹保留帧数 (默认 30)
        max_center_dist: 中心距离兜底匹配阈值(像素) (默认 80)
    """

    def __init__(self, track_thresh=0.5, match_thresh=0.3, track_buffer=30, max_center_dist=80.0):
        self.track_thresh = float(track_thresh)
        self.match_thresh = float(match_thresh)
        self.track_buffer = int(track_buffer)
        self.max_center_dist = float(max_center_dist)
        self.frame_id = 0
        self.tracked_stracks = []   # 当前跟踪中
        self.lost_stracks = []      # 暂时丢失
        self.removed_stracks = []   # 已删除
        STrack.reset_id()

    def reset(self):
        """重置跟踪器状态"""
        self.frame_id = 0
        self.tracked_stracks.clear()
        self.lost_stracks.clear()
        self.removed_stracks.clear()
        STrack.reset_id()

    def update(self, boxes, scores=None, class_ids=None):
        """
        用当前帧检测结果更新跟踪器

        Args:
            boxes: (N, 4) numpy array [x1, y1, x2, y2]
            scores: (N,) 置信度数组, 若为 None 则全部设为 1.0
            class_ids: (N,) 类别ID数组, 若为 None 则全部设为 0

        Returns:
            list[STrack]: 当前帧所有激活的轨迹
        """
        self.frame_id += 1

        if boxes is None or len(boxes) == 0:
            # 无检测，所有轨迹标记丢失
            for t in self.tracked_stracks:
                t.mark_lost()
                self.lost_stracks.append(t)
            self.tracked_stracks.clear()
            self._remove_expired_lost()
            return self._output_stracks()

        boxes = np.array(boxes, dtype=np.float32)
        n = len(boxes)
        if scores is None:
            scores = np.ones(n, dtype=np.float32)
        else:
            scores = np.array(scores, dtype=np.float32)
        if class_ids is None:
            class_ids = np.zeros(n, dtype=np.int32)
        else:
            class_ids = np.array(class_ids, dtype=np.int32)

        # 创建检测对象
        detections = []
        for i in range(n):
            det = STrack(boxes[i], scores[i], class_ids[i])
            detections.append(det)

        # 分高低分检测
        high_dets = [d for d in detections if d.score >= self.track_thresh]
        low_dets = [d for d in detections if d.score < self.track_thresh]

        # 对已有轨迹做预测
        strack_pool = self.tracked_stracks + self.lost_stracks
        for t in strack_pool:
            t.predict()

        # ========== 第一轮: 高分检测 vs 所有轨迹 ==========
        if len(strack_pool) > 0 and len(high_dets) > 0:
            iou_matrix = _iou_batch(
                [t.bbox for t in strack_pool],
                [d.bbox for d in high_dets],
            )
            cost_matrix = 1.0 - iou_matrix
            matches_1, u_tracks_1, u_dets_1 = _linear_assignment(cost_matrix, 1.0 - self.match_thresh)
        else:
            matches_1 = []
            u_tracks_1 = list(range(len(strack_pool)))
            u_dets_1 = list(range(len(high_dets)))

        activated = []
        refound = []

        for t_idx, d_idx in matches_1:
            track = strack_pool[t_idx]
            det = high_dets[d_idx]
            if track.state == STrack.State.TRACKED:
                track.update(det, self.frame_id)
                activated.append(track)
            else:
                track.re_activate(det, self.frame_id)
                refound.append(track)

        # ========== 第二轮: 低分检测 vs 未匹配的 tracked 轨迹 ==========
        unmatched_tracked = [strack_pool[i] for i in u_tracks_1 if strack_pool[i].state == STrack.State.TRACKED]
        if len(unmatched_tracked) > 0 and len(low_dets) > 0:
            iou_matrix_2 = _iou_batch(
                [t.bbox for t in unmatched_tracked],
                [d.bbox for d in low_dets],
            )
            cost_matrix_2 = 1.0 - iou_matrix_2
            matches_2, u_tracks_2, _ = _linear_assignment(cost_matrix_2, 1.0 - 0.5)
        else:
            matches_2 = []
            u_tracks_2 = list(range(len(unmatched_tracked)))

        for t_idx, d_idx in matches_2:
            track = unmatched_tracked[t_idx]
            det = low_dets[d_idx]
            track.update(det, self.frame_id)
            activated.append(track)

        # 未匹配的 tracked 轨迹 → 先尝试中心距离兜底匹配再标记丢失
        still_unmatched_tracked = []
        if len(u_tracks_2) > 0 and self.max_center_dist > 0:
            # 收集仍未匹配的 tracked 轨迹和未匹配的高分检测
            remaining_tracked = [unmatched_tracked[i] for i in u_tracks_2]
            remaining_high = [high_dets[i] for i in u_dets_1]
            if len(remaining_tracked) > 0 and len(remaining_high) > 0:
                tc = np.array([t.center for t in remaining_tracked], dtype=np.float32)
                dc = np.array([d.center for d in remaining_high], dtype=np.float32)
                diff = tc[:, None, :] - dc[None, :, :]
                dist_mat = np.sqrt(np.sum(diff ** 2, axis=2))
                matches_2b, u_tracks_2b, u_dets_2b = _linear_assignment(dist_mat, self.max_center_dist)
                matched_det_set = set()
                for t_idx, d_idx in matches_2b:
                    track = remaining_tracked[t_idx]
                    det = remaining_high[d_idx]
                    track.update(det, self.frame_id)
                    activated.append(track)
                    matched_det_set.add(d_idx)
                # 更新未匹配检测索引
                u_dets_1 = [u_dets_1[i] for i in range(len(u_dets_1)) if i not in matched_det_set]
                # 仍未匹配的 tracked 轨迹
                for i in u_tracks_2b:
                    still_unmatched_tracked.append(remaining_tracked[i])
            else:
                for i in u_tracks_2:
                    still_unmatched_tracked.append(unmatched_tracked[i])
        else:
            for i in u_tracks_2:
                still_unmatched_tracked.append(unmatched_tracked[i])

        for track in still_unmatched_tracked:
            if track.state != STrack.State.LOST:
                track.mark_lost()
                self.lost_stracks.append(track)

        # ========== 第三轮: 中心距离兜底 — 未匹配的 lost 轨迹 vs 未匹配的高分检测 ==========
        # IoU 在快速移动/后坐力时可能为0，用中心距离兜底恢复丢失轨迹
        unmatched_lost = [strack_pool[i] for i in u_tracks_1 if strack_pool[i].state == STrack.State.LOST]
        remaining_high_dets = [high_dets[i] for i in u_dets_1]
        if len(unmatched_lost) > 0 and len(remaining_high_dets) > 0 and self.max_center_dist > 0:
            track_centers = np.array([t.center for t in unmatched_lost], dtype=np.float32)
            det_centers = np.array([d.center for d in remaining_high_dets], dtype=np.float32)
            diff = track_centers[:, None, :] - det_centers[None, :, :]
            dist_matrix = np.sqrt(np.sum(diff ** 2, axis=2))
            matches_3, _, u_dets_3 = _linear_assignment(dist_matrix, self.max_center_dist)
            matched_det_indices = set()
            for t_idx, d_idx in matches_3:
                track = unmatched_lost[t_idx]
                det = remaining_high_dets[d_idx]
                track.re_activate(det, self.frame_id)
                refound.append(track)
                matched_det_indices.add(d_idx)
            # 更新 u_dets_1 为仍未匹配的检测
            u_dets_1 = [u_dets_1[i] for i in range(len(u_dets_1)) if i not in matched_det_indices]

        # ========== 新轨迹: 未匹配的高分检测 ==========
        for i in u_dets_1:
            det = high_dets[i]
            det.activate(self.frame_id)
            activated.append(det)

        # 更新 tracked 列表
        self.tracked_stracks = [t for t in self.tracked_stracks if t.state == STrack.State.TRACKED]
        self.tracked_stracks = _merge_stracks(self.tracked_stracks, activated)
        self.tracked_stracks = _merge_stracks(self.tracked_stracks, refound)

        # 从 lost 中移除已重新激活的
        self.lost_stracks = _sub_stracks(self.lost_stracks, self.tracked_stracks)

        # 清除过期 lost 轨迹
        self._remove_expired_lost()

        return self._output_stracks()

    def _remove_expired_lost(self):
        """移除超过 track_buffer 帧的丢失轨迹"""
        remaining = []
        for t in self.lost_stracks:
            if self.frame_id - t.frame_id <= self.track_buffer:
                remaining.append(t)
            else:
                t.mark_removed()
        self.lost_stracks = remaining

    def _output_stracks(self):
        """返回当前所有激活的轨迹"""
        return [t for t in self.tracked_stracks if t.is_activated]

    def get_track_by_id(self, track_id):
        """根据 track_id 查找轨迹（在所有池中查找）"""
        for t in self.tracked_stracks:
            if t.track_id == track_id:
                return t
        for t in self.lost_stracks:
            if t.track_id == track_id:
                return t
        return None


def _merge_stracks(list_a, list_b):
    """合并两个轨迹列表，去重（按 track_id）"""
    ids_a = set(t.track_id for t in list_a)
    merged = list(list_a)
    for t in list_b:
        if t.track_id not in ids_a:
            merged.append(t)
            ids_a.add(t.track_id)
    return merged


def _sub_stracks(list_a, list_b):
    """从 list_a 中移除 list_b 中存在的轨迹"""
    ids_b = set(t.track_id for t in list_b)
    return [t for t in list_a if t.track_id not in ids_b]
