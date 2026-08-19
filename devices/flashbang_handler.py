# -*- coding: utf-8 -*-
"""
闪光弹自动背闪模块 — 从 core.py 抽取的独立组件

职责：
  - 检测闪光弹目标（class_id==4）
  - 判断闪光弹方向并决定转向
  - 执行背闪转向 + 回正（直线/曲线）
  - 冷却时间管理
"""
import math
import random
import time
import threading

try:
    from pyclick import HumanCurve
except ImportError:
    HumanCurve = None


class FlashbangHandler:
    """闪光弹检测与背闪执行器，不依赖 GUI"""

    def __init__(self, move_r_func):
        """
        Args:
            move_r_func: 鼠标相对移动函数 move_r(dx, dy)
        """
        self._move_r = move_r_func

        # ── 状态 ──
        self.last_time = 0
        self.cooldown = 1.0
        self.is_turning_back = False
        self.turn_back_start_time = 0
        self._actual_x = 0
        self._actual_y = 0

    # ────────────────────────────────────────────
    #  检测入口
    # ────────────────────────────────────────────

    def detect_and_handle(self, boxes, class_ids, model_w, model_h, cfg, scores=None):
        """
        检测闪光弹并异步执行背闪

        Args:
            boxes: 检测框数组
            class_ids: 类别 ID 数组
            model_w, model_h: 模型输入尺寸
            cfg: config['auto_flashbang'] 子配置
            scores: 置信度数组（可选）
        """
        now = time.time()
        if now - self.last_time < self.cooldown:
            return

        min_conf = cfg['min_confidence']
        min_size = cfg['min_size']
        fb_indices = []
        class4 = False

        for i, cid in enumerate(class_ids):
            if cid != 4:
                continue
            class4 = True
            conf = scores[i] if scores is not None else 1.0
            box = boxes[i]
            try:
                x1, y1, x2, y2 = box[0], box[1], box[2], box[3]
                w = abs(x2 - x1)
                h = abs(y2 - y1)
                ms = min(w, h)
                if w == 0 or h == 0:
                    continue
            except (IndexError, TypeError):
                continue
            print(f'发现类别4: 置信度={conf:.3f}, 尺寸={w:.1f}x{h:.1f}, 最小边={ms:.1f}')
            if scores is not None and scores[i] < min_conf:
                print(f'  跳过: 置信度{conf:.3f} < {min_conf}')
            elif ms < min_size:
                print(f'  跳过: 尺寸{ms:.1f} < {min_size}')
            else:
                fb_indices.append(i)

        if class4 and not fb_indices:
            print('检测到类别4但全部被过滤')
        if not fb_indices:
            return

        print(f'检测到{len(fb_indices)}个有效闪光弹，准备执行背闪')
        left = right = 0
        cx = model_w / 2
        for idx in fb_indices:
            box = boxes[idx]
            try:
                fb_cx = (box[0] + box[2]) / 2
                if fb_cx < cx:
                    left += 1
                else:
                    right += 1
            except (IndexError, TypeError):
                pass

        if left > right:
            d = -1
        elif right > left:
            d = 1
        else:
            d = random.choice([-1, 1])
        dt = '左' if d == -1 else '右'
        print(f'闪光弹分布: 左侧{left}个，右侧{right}个，向{dt}背闪')

        self.last_time = now
        delay = cfg['delay_ms']
        print(f'将在{delay}ms后执行背闪')
        threading.Timer(delay / 1000.0, self._turn, args=(d, cfg)).start()

    # ────────────────────────────────────────────
    #  转向 & 回正
    # ────────────────────────────────────────────

    def _turn(self, direction, cfg):
        if self.is_turning_back:
            return
        angle = cfg['turn_angle'] * direction
        sensitivity = cfg['sensitivity_multiplier']
        mx = int(angle * sensitivity)
        print(f'执行背闪: 转向{angle}度, 鼠标移动{mx}像素')
        self._actual_x = mx
        self._actual_y = 0
        try:
            if cfg['use_curve']:
                actual = self._ultra_fast_move(mx, 0, cfg)
                if actual:
                    self._actual_x, self._actual_y = actual
            else:
                self._move_r(mx, 0)
            print(f'实际移动距离: X={self._actual_x}, Y={self._actual_y}')
            ret_delay = cfg['return_delay'] / 1000.0
            threading.Timer(ret_delay, self._return, args=(direction, cfg)).start()
        except Exception as e:
            print(f'执行背闪转向时出错: {e}')

    def _return(self, orig_dir, cfg):
        if self.is_turning_back:
            return
        self.is_turning_back = True
        self.turn_back_start_time = time.time()
        try:
            rx, ry = -self._actual_x, -self._actual_y
            print(f'执行精确回转: X={rx}, Y={ry}像素')
            if cfg['use_curve']:
                self._ultra_fast_move(rx, ry, cfg)
            else:
                self._move_r(rx, ry)
            self._actual_x = 0
            self._actual_y = 0
        except Exception as e:
            print(f'执行回转时出错: {e}')
        finally:
            time.sleep(0.05)
            self.is_turning_back = False

    # ────────────────────────────────────────────
    #  曲线移动
    # ────────────────────────────────────────────

    def _make_curve(self, dx, dy, cfg, full_cfg, knots_override=None, distortion_scale=1.0):
        """生成 HumanCurve 轨迹，返回 points 列表或 None
        
        Args:
            cfg: auto_flashbang 子配置
            full_cfg: 顶层 config（含 offset_boundary_x 等曲线参数）
        """
        if HumanCurve is None:
            return None
        knots = knots_override if knots_override is not None else cfg.get('curve_knots', 10)
        try:
            c = HumanCurve(
                (0, 0), (round(dx), round(dy)),
                offsetBoundaryX=full_cfg.get('offset_boundary_x', 10),
                offsetBoundaryY=full_cfg.get('offset_boundary_y', 10),
                knotsCount=knots,
                distortionMean=full_cfg.get('distortion_mean', 1.0) * distortion_scale,
                distortionStdev=full_cfg.get('distortion_st_dev', 1.0) * distortion_scale,
                distortionFrequency=full_cfg.get('distortion_frequency', 0.5) * distortion_scale,
                targetPoints=full_cfg.get('target_points', 5),
            )
            pts = c.points
            return None if isinstance(pts, tuple) else pts
        except Exception:
            return None

    def curve_move(self, dx, dy, cfg, full_cfg):
        """背闪曲线移动（人性化缓动）"""
        pts = self._make_curve(dx, dy, cfg, full_cfg)
        if pts is None:
            print('曲线生成失败，使用直线移动')
            self._move_r(round(dx), round(dy))
            return

        moves = self._points_to_moves(pts, dx, dy)
        if not moves:
            self._move_r(round(dx), round(dy))
            return
        for mx, my in moves:
            if mx != 0 or my != 0:
                self._move_r(mx, my)
        print(f'背闪曲线移动完成，总帧数: {len(moves)}')

    def curve_move_with_tracking(self, dx, dy, cfg, full_cfg):
        """曲线移动并返回实际移动量 (ax, ay)"""
        pts = self._make_curve(dx, dy, cfg, full_cfg)
        if pts is None:
            print('曲线生成失败，使用直线移动')
            self._move_r(round(dx), round(dy))
            return (dx, dy)

        moves = self._points_to_moves(pts, dx, dy)
        if not moves:
            self._move_r(round(dx), round(dy))
            return (dx, dy)
        ax = ay = 0
        for mx, my in moves:
            if mx != 0 or my != 0:
                self._move_r(mx, my)
                ax += mx
                ay += my
        print(f'背闪曲线移动完成，实际移动: X={ax}, Y={ay}')
        return (ax, ay)

    def _ultra_fast_move(self, dx, dy, cfg):
        """超快速背闪：大步长无延迟"""
        try:
            print(f'超快速背闪移动: X={dx}, Y={dy}')
            dist = math.sqrt(dx * dx + dy * dy)
            if dist <= 100:
                rx, ry = round(dx), round(dy)
                self._move_r(rx, ry)
                return (rx, ry)
            elif dist <= 500:
                s1x, s1y = round(dx * 0.6), round(dy * 0.6)
                s2x, s2y = round(dx - s1x), round(dy - s1y)
                self._move_r(s1x, s1y)
                self._move_r(s2x, s2y)
                return (s1x + s2x, s1y + s2y)
            else:
                s1x, s1y = round(dx * 0.5), round(dy * 0.5)
                s2x, s2y = round(dx * 0.3), round(dy * 0.3)
                s3x, s3y = round(dx - s1x - s2x), round(dy - s1y - s2y)
                self._move_r(s1x, s1y)
                self._move_r(s2x, s2y)
                self._move_r(s3x, s3y)
                return (s1x + s2x + s3x, s1y + s2y + s3y)
        except Exception as e:
            print(f'超快速移动出错: {e}')
            self._move_r(round(dx), round(dy))
            return (dx, dy)

    @staticmethod
    def _points_to_moves(pts, target_x, target_y):
        """将曲线点转为增量列表，做距离修正"""
        moves = []
        tx = ty = 0.0
        for i in range(1, len(pts)):
            x = pts[i][0] - pts[i - 1][0]
            y = pts[i][1] - pts[i - 1][1]
            if abs(x) < 0.1 and abs(y) < 0.1:
                continue
            moves.append((x, y))
            tx += x
            ty += y
        if not moves:
            return []
        if abs(tx - target_x) > 1 or abs(ty - target_y) > 1:
            cx = target_x / tx if tx != 0 else 1
            cy = target_y / ty if ty != 0 else 1
            moves = [(dx * cx, dy * cy) for dx, dy in moves]
        return [(round(x), round(y)) for x, y in moves]
