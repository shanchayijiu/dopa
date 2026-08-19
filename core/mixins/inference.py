# -*- coding: utf-8 -*-
"""推理调度 Mixin — 从 core.py 提取的推理引擎管理方法。

包含模型推理循环(infer)、引擎刷新(refresh_engine)、引擎创建(_create_engine_from_bytes)、
队列清理(_clear_queues)、状态重置(_reset_aim_states)、v11onnx 模型准备。
所有方法操作 self.* 属性，由 Valorant.__init__ 创建，通过 mix-in 继承可用。
"""
import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor
import queue

import numpy as np
import cv2

from inference.infer_class import OnnxRuntimeDmlEngine
from inference.infer_function import nms, nms_v8, read_img
from inference.v11onnx_support import (
    should_use_v11onnx,
    resolve_runtime_config,
    build_ort_runtime_components,
    discover_v11onnx_model,
    get_default_runtime_config,
    ModelValidationError,
    validate_v11onnx_model,
)
from settings import config_manager as cfgmgr
from settings.remote_config import save_remote_config

# TensorRT 符号从 core 延迟导入（此时 core 已完成 TensorRT 检测，尚未定义 class）
from ..runtime import TENSORRT_AVAILABLE, TensorRTInferenceEngine, ensure_engine_from_memory
from util.diagnostics import note_suppressed


class InferenceMixin:
    """推理调度 Mixin。

    方法依赖 Valorant.__init__ 中建立的属性：
      self.engine / self.config / self.group / self.que_aim / self.que_trigger /
      self.screenshot_manager / self.infer_debug / self.end 等。
    """

    def _harmonize_v8_boxes(self, boxes, input_w, input_h):
        """
        统一 v8/v11 输出框到内部 xywh 像素坐标格式，解决：
        1) 部分模型输出 xyxy，导致框偏移/不完整
        2) 部分模型输出归一化坐标，导致框尺度异常
        """
        boxes = np.asarray(boxes, dtype=np.float32)
        if boxes.ndim != 2 or boxes.shape[1] < 4 or len(boxes) == 0:
            return boxes

        fixed = np.nan_to_num(boxes[:, :4], nan=0.0, posinf=0.0, neginf=0.0)

        # 判断是否更像 xyxy（大部分框满足 x2>x1, y2>y1）
        xyxy_mask = (fixed[:, 2] > fixed[:, 0]) & (fixed[:, 3] > fixed[:, 1])
        if xyxy_mask.sum() > len(fixed) * 0.8:
            x1, y1, x2, y2 = fixed[:, 0], fixed[:, 1], fixed[:, 2], fixed[:, 3]
            w = np.maximum(1e-6, x2 - x1)
            h = np.maximum(1e-6, y2 - y1)
            cx = x1 + w * 0.5
            cy = y1 + h * 0.5
            fixed = np.stack([cx, cy, w, h], axis=1)

        # 归一化坐标自动放缩到像素空间
        max_abs = float(np.max(np.abs(fixed))) if fixed.size else 0.0
        if max_abs <= 4.0:
            fixed[:, 0] *= float(input_w)
            fixed[:, 2] *= float(input_w)
            fixed[:, 1] *= float(input_h)
            fixed[:, 3] *= float(input_h)

        fixed[:, 2] = np.clip(fixed[:, 2], 1.0, float(input_w))
        fixed[:, 3] = np.clip(fixed[:, 3], 1.0, float(input_h))
        fixed[:, 0] = np.clip(fixed[:, 0], 0.0, float(input_w) - 1.0)
        fixed[:, 1] = np.clip(fixed[:, 1], 0.0, float(input_h) - 1.0)
        return fixed

    def infer(self):
        self.time_begin_period(1)
        if self.engine is None:
            model_path = self.config['groups'][self.group]['infer_model']
            while self.engine is None and (not self.end):
                time.sleep(0.1)
                if self.end:
                    return
            if self.engine is None:
                return
        group_cfg = self.config['groups'][self.group]
        is_v11_variant = str(group_cfg.get('model_variant', '')).strip().lower() == 'v11onnx'
        # v11onnx 与 v8 输出格式一致，统一复用 v8 后处理分支。
        is_v8 = bool(group_cfg.get('is_v8', False) or is_v11_variant)
        if is_v8:
            class_num = self.engine.get_class_num_v8()
        else:
            class_num = self.engine.get_class_num()
        input_shape_weight = self.engine.get_input_shape()[3]
        input_shape_height = self.engine.get_input_shape()[2]
        print('模型输入尺寸：', input_shape_weight, input_shape_height)
        # 预计算输出列数，避免每帧查询
        if is_v8:
            _output_cols = class_num + 4
        else:
            _output_cols = class_num + 5
        frame_count = 0
        start_time = time.perf_counter()
        last_fps_update_time = time.perf_counter()
        fps_text = 'FPS: 0.00'
        self.fps = 0
        last_latency_text = 'latency: 0.00ms'
        latency_values = []
        last_latency_update_time = time.perf_counter()
        display_latency_ms = 0.0
        screenshot_region = ((self.screen_width - input_shape_weight) // 2, (self.screen_height - input_shape_height) // 2, (self.screen_width - input_shape_weight) // 2 + input_shape_weight, (self.screen_height - input_shape_height) // 2 + input_shape_height)
        print_fps = self.config['print_fps']
        infer_debug = self.config['infer_debug']
        frame_skip_ratio = self.config.get('frame_skip_ratio', 0)
        frame_skip_counter = 0
        # 预处理流水线：在 GPU 推理帧 N 时，CPU 同时截屏+预处理帧 N+1
        _preprocess_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='preproc')
        _preprocess_future = None
        _preprocess_screenshot = None  # 保存截屏原图用于后续 debug 显示
        aim_boxes = None  # 初始化，避免每帧 locals() 查找

        def _capture_and_preprocess():
            """截屏 + 准心找色 + 预处理，在后台线程执行"""
            ss = self.screenshot_manager.get_screenshot(screenshot_region)
            if ss is None:
                return None, None
            self.update_crosshair_tracking(ss)
            blob = read_img(ss, (input_shape_weight, input_shape_height))
            return ss, blob

        while self.running:
            if frame_skip_ratio > 0:
                frame_skip_counter += 1
                if frame_skip_counter % (frame_skip_ratio + 1)!= 0:
                    continue
            # 流水线取结果：如果有预处理 future，等待它完成
            if _preprocess_future is not None:
                try:
                    _preprocess_screenshot, img_input = _preprocess_future.result()
                except Exception:
                    _preprocess_screenshot, img_input = None, None
                _preprocess_future = None
                if img_input is None:
                    # 预处理失败，同步重试
                    _preprocess_screenshot = self.screenshot_manager.get_screenshot(screenshot_region)
                    if _preprocess_screenshot is None:
                        continue
                    self.update_crosshair_tracking(_preprocess_screenshot)
                    img_input = read_img(_preprocess_screenshot, (input_shape_weight, input_shape_height))
            else:
                # 首帧或回退：同步执行
                _preprocess_screenshot = self.screenshot_manager.get_screenshot(screenshot_region)
                if _preprocess_screenshot is None:
                    continue
                self.update_crosshair_tracking(_preprocess_screenshot)
                img_input = read_img(_preprocess_screenshot, (input_shape_weight, input_shape_height))
            screenshot = _preprocess_screenshot
            frame_count += 1
            current_fps_time = time.perf_counter()
            if current_fps_time - last_fps_update_time >= 1.0:
                time_elapsed = current_fps_time - start_time
                if time_elapsed > 0:
                    self.fps = frame_count / time_elapsed
                    fps_text = f'FPS: {self.fps:.2f}'
                    if print_fps:
                        print(fps_text)
                frame_count = 0
                start_time = current_fps_time
                last_fps_update_time = current_fps_time
            # 提交下一帧预处理（与本帧推理并行）
            _preprocess_future = _preprocess_executor.submit(_capture_and_preprocess)
            infer_start_time = time.perf_counter()
            try:
                outputs = self.engine.infer(img_input)
            except Exception as infer_e:
                err_text = str(infer_e)
                if 'Got invalid dimensions for input' in err_text or 'INVALID_ARGUMENT' in err_text:
                    try:
                        shape = self.engine.get_input_shape()
                        new_w = int(shape[3])
                        new_h = int(shape[2])
                        if new_w > 0 and new_h > 0:
                            input_shape_weight = new_w
                            input_shape_height = new_h
                            screenshot_region = (
                                (self.screen_width - input_shape_weight) // 2,
                                (self.screen_height - input_shape_height) // 2,
                                (self.screen_width - input_shape_weight) // 2 + input_shape_weight,
                                (self.screen_height - input_shape_height) // 2 + input_shape_height,
                            )
                            print(f"[Infer] 检测到模型输入尺寸不一致，已自动切换为: {input_shape_weight} {input_shape_height}")
                        else:
                            print(f"[Infer] 输入尺寸异常，无法自动修复: {infer_e}")
                    except Exception as shape_e:
                        print(f"[Infer] 推理输入尺寸异常: {infer_e}; 读取形状失败: {shape_e}")
                else:
                    print(f"[Infer] 推理异常: {infer_e}")
                time.sleep(0.01)
                continue
            infer_end_time = time.perf_counter()
            current_infer_time_ms = (infer_end_time - infer_start_time) * 1000
            latency_values.append(current_infer_time_ms)
            if infer_end_time - last_latency_update_time >= 1.0 and latency_values:
                avg_latency = sum(latency_values) / len(latency_values)
                display_latency_ms = avg_latency
                last_latency_text = f'latency: {avg_latency:.2f}ms'
                latency_values = []
                last_latency_update_time = infer_end_time
            infer_time_ms = display_latency_ms
            pred = outputs[0]
            if pred.ndim == 1:
                C = _output_cols
                if pred.size % C!= 0:
                    raise ValueError(f'推理输出长度{pred.size}不能整除每行特征数{C}，请检查模型！')
                pred = pred.reshape((-1), C)
            class_aim_positions = self.pressed_key_config.get('class_aim_positions', {})
            if not isinstance(class_aim_positions, dict):
                class_aim_positions = {}
            # 缓存逐类阈值，仅在 pressed_key_config 变化时重建
            _pkc_id = id(self.pressed_key_config)
            if getattr(self, '_cached_pkc_id', None) != _pkc_id:
                min_confidence_threshold = 0.05
                class_confidence_thresholds = {}
                class_iou_thresholds = {}
                for class_str, config in class_aim_positions.items():
                    if isinstance(config, dict):
                        conf_thresh = config.get('confidence_threshold', 0.5)
                        iou_thresh = config.get('iou_t', 1.0)
                        class_confidence_thresholds[int(class_str)] = conf_thresh
                        class_iou_thresholds[int(class_str)] = iou_thresh
                        min_confidence_threshold = min(min_confidence_threshold, conf_thresh)
                if not class_confidence_thresholds:
                    confidence_threshold = self.pressed_key_config.get('confidence_threshold', 0.5)
                    iou_t = self.pressed_key_config.get('iou_t', 1.0)
                else:
                    confidence_threshold = min_confidence_threshold
                    iou_t = min(class_iou_thresholds.values()) if class_iou_thresholds else 1.0
                self._cached_pkc_id = _pkc_id
                self._cached_class_conf = class_confidence_thresholds
                self._cached_class_iou = class_iou_thresholds
                self._cached_conf_thresh = confidence_threshold
                self._cached_iou_t = iou_t
                # 缓存 selected_classes_set 和对应 numpy 数组
                _sel_classes = self.pressed_key_config.get('classes', [])
                _sel_set = set(_sel_classes) if _sel_classes else set()
                if is_v8 and class_num == 1 and _sel_set and 0 not in _sel_set:
                    _sel_set.add(0)
                self._cached_selected_set = _sel_set
                self._cached_selected_arr = np.array(list(_sel_set), dtype=int) if _sel_set else None
            else:
                class_confidence_thresholds = self._cached_class_conf
                class_iou_thresholds = self._cached_class_iou
                confidence_threshold = self._cached_conf_thresh
                iou_t = self._cached_iou_t
            selected_classes_set = self._cached_selected_set
            _cached_selected_arr = self._cached_selected_arr
            if is_v8:
                adaptive_nms_enabled = (
                    self.config['small_target_enhancement']['enabled']
                    and self.config['small_target_enhancement']['adaptive_nms']
                )
                if is_v11_variant and class_num == 1:
                    # 单类 v11 场景下关闭自适应 NMS，减少框抖动与漏检。
                    adaptive_nms_enabled = False
                boxes, scores, classes = nms_v8(pred, confidence_threshold, iou_t, adaptive_nms_enabled)
            else:
                boxes, scores, classes = nms(pred, confidence_threshold, iou_t, class_num)
            if is_v8 and len(boxes) > 0:
                boxes = self._harmonize_v8_boxes(
                    boxes=boxes,
                    input_w=input_shape_weight,
                    input_h=input_shape_height,
                )
            
            current_selected_classes = self.pressed_key_config.get('classes', [])
            class_ids = []
            aim_boxes = None
            if len(boxes) > 0:
                if is_v8:
                    all_class_ids = classes.astype(int)
                else:
                    all_class_ids = np.argmax(classes, axis=1).astype(int)
                if selected_classes_set:
                    mask = np.isin(all_class_ids, _cached_selected_arr)
                    boxes = boxes[mask]
                    scores = scores[mask]
                    classes = classes[mask]
                    class_ids = all_class_ids[mask].tolist()
                    if class_confidence_thresholds and len(boxes) > 0:
                        # 向量化逐类置信度过滤
                        _default_conf = 0.5
                        _thresholds = np.array([class_confidence_thresholds.get(c, _default_conf) for c in class_ids], dtype=np.float32)
                        confidence_mask = scores >= _thresholds
                        if not confidence_mask.all():
                            boxes = boxes[confidence_mask]
                            scores = scores[confidence_mask]
                            classes = classes[confidence_mask]
                            class_ids = [class_ids[i] for i, keep in enumerate(confidence_mask) if keep]
                else:
                    boxes = []
                    scores = []
                    classes = []
                    class_ids = []
                    aim_boxes = []
            if self.config['auto_flashbang']['enabled'] and len(boxes) > 0 and (len(class_ids) > 0):
                if self.is_using_dopa_model():
                    self._get_flashbang().detect_and_handle(boxes, class_ids, input_shape_weight, input_shape_height, self.config['auto_flashbang'], scores)
                elif 4 in class_ids and (not hasattr(self, '_dopa_warning_shown')):
                    print('自动背闪功能仅支持ZTX模型，当前模型不支持')
                    self._dopa_warning_shown = True
            elif self.config['auto_flashbang']['enabled']:
                if len(class_ids) > 0 and 4 in class_ids:
                    if self.is_using_dopa_model():
                        print('检测到类别4，但boxes为空或过滤后为空')
                    elif not hasattr(self, '_dopa_warning_shown'):
                        print('自动背闪功能仅支持ZTX模型')
                        self._dopa_warning_shown = True
            if len(boxes) > 0:
                if self.aim_key_status:
                    try:
                        payload = {
                            'frame_id': frame_count,
                            'boxes': boxes,
                            'class_ids': class_ids,
                            'input_w': input_shape_weight,
                            'input_h': input_shape_height,
                        }
                        self.que_aim.put_nowait(payload)
                    except queue.Full:
                        try:
                            self.que_aim.get_nowait()
                        except queue.Empty:
                            pass
                        self.que_aim.put_nowait(payload)
                trigger_enabled = self.pressed_key_config['trigger']['status']
                if trigger_enabled:
                    try:
                        self.que_trigger.put_nowait(boxes)
                    except queue.Full:
                        try:
                            self.que_trigger.get_nowait()
                        except queue.Empty:
                            pass
                        self.que_trigger.put_nowait(boxes)
            # 射击时降低 debug 刷新频率（每6帧），减少 OSD 渲染开销
            _debug_interval = 6 if self.aim_key_status else 3
            if infer_debug and self.screenshot_manager and (frame_count % _debug_interval == 0):
                if self.aim_key_status:
                    current_key = self.old_pressed_aim_key
                else:
                    current_key = self.select_key if hasattr(self, 'select_key') and self.select_key else self.old_pressed_aim_key
                current_scope = 0
                if current_key and current_key in self.config['groups'][self.group]['aim_keys']:
                    current_scope = self.get_dynamic_aim_scope()
                
                display_boxes = boxes
                display_classes = classes
                display_scores = scores
                
                is_v8 = bool(
                    self.config['groups'][self.group].get('is_v8', False)
                    or str(self.config['groups'][self.group].get('model_variant', '')).strip().lower() == 'v11onnx'
                )
                current_move_deadzone = self.pressed_key_config.get('move_deadzone', 1.0)
                current_smooth_deadzone = self.pressed_key_config.get('smooth_deadzone', 0.0)
                crosshair_cfg = self.config.get('crosshair_color_lock', {})
                crosshair_enabled = isinstance(crosshair_cfg, dict) and crosshair_cfg.get('enabled', False)
                show_crosshair = bool(crosshair_cfg.get('show_crosshair', True))
                show_lock_box = bool(crosshair_cfg.get('show_lock_box', True))
                lock_box = self._crosshair_tracker.lock_box if crosshair_enabled else None
                
                # 如果开启了二值化显示，使用 mask 替换原图
                final_screenshot = screenshot
                _dbg_mask = self._crosshair_tracker.debug_mask
                if crosshair_enabled and crosshair_cfg.get('show_mask', False) and _dbg_mask is not None:
                    # 确保尺寸一致
                    if _dbg_mask.shape == screenshot.shape:
                        final_screenshot = _dbg_mask
                    else:
                        try:
                            final_screenshot = cv2.resize(_dbg_mask, (screenshot.shape[1], screenshot.shape[0]))
                        except Exception as e:
                            print(f'debug mask resize失败: {e}')

                self.screenshot_manager.put_screenshot_result(
                    final_screenshot,
                    display_boxes,
                    display_scores,
                    display_classes,
                    fps_text,
                    infer_time_ms,
                    current_key,
                    current_scope,
                    self.aim_key_status,
                    is_v8,
                    current_move_deadzone,
                    current_smooth_deadzone,
                    lock_box,
                    show_crosshair,
                    show_lock_box,
                    crosshair_enabled,
                )
                self.showed = True
        self.time_end_period(1)

    def _update_dynamic_aim_scope(self):
        # 根据锁定状态与转移延迟，线性调整瞄准范围。
        now_ms = time.time() * 1000
        cfg = self.pressed_key_config
        base_scope = float(cfg.get('aim_bot_scope', 0) or 0)
        if base_scope <= 0:
            self._dynamic_scope['value'] = 0
            self._dynamic_scope['phase'] = 'idle'
            self._dynamic_scope['last_ms'] = now_ms
            return 0
        dyn_cfg = cfg.get('dynamic_scope', {}) or {}
        enabled = bool(dyn_cfg.get('enabled', False))
        min_ratio = dyn_cfg.get('min_ratio', None)
        if min_ratio is not None:
            try:
                min_ratio = float(min_ratio)
            except Exception:
                min_ratio = 0.5
            min_scope = base_scope * max(0, min(1, float(min_ratio)))
        else:
            try:
                min_scope = float(dyn_cfg.get('min_scope', base_scope))
            except Exception:
                min_scope = base_scope
        shrink_ms = int(dyn_cfg.get('shrink_duration_ms', 300))
        recover_ms = int(dyn_cfg.get('recover_duration_ms', 300))
        lock_active = self.last_target_count > 0 and not self.is_waiting_for_switch
        if self._dynamic_scope_lock_active_prev and not lock_active:
            if not (cfg.get('target_switch_delay', 0) and self.is_waiting_for_switch):
                self._dynamic_scope['phase'] = 'recover'
                self._dynamic_scope['last_ms'] = now_ms
        if not self._dynamic_scope_lock_active_prev and lock_active:
            self._dynamic_scope['phase'] = 'shrink'
            self._dynamic_scope['last_ms'] = now_ms
        self._dynamic_scope_lock_active_prev = lock_active
        if not enabled:
            self._dynamic_scope['value'] = base_scope
            self._dynamic_scope['phase'] = 'idle'
            self._dynamic_scope['last_ms'] = now_ms
            return base_scope
        phase = self._dynamic_scope['phase']
        elapsed = max(0, now_ms - self._dynamic_scope['last_ms'])
        if phase == 'shrink':
            if shrink_ms <= 0:
                val = min_scope
            else:
                t = max(0, min(1, elapsed / float(shrink_ms)))
                val = base_scope + (min_scope - base_scope) * t
            self._dynamic_scope['value'] = val
            if elapsed >= shrink_ms:
                self._dynamic_scope['phase'] = 'hold'
                self._dynamic_scope['last_ms'] = now_ms
        elif phase == 'hold':
            self._dynamic_scope['value'] = min_scope
        elif phase == 'recover':
            if recover_ms <= 0:
                val = base_scope
            else:
                t = max(0, min(1, elapsed / float(recover_ms)))
                val = min_scope + (base_scope - min_scope) * t
            self._dynamic_scope['value'] = val
            if elapsed >= recover_ms:
                self._dynamic_scope['phase'] = 'idle'
                self._dynamic_scope['last_ms'] = now_ms
        else:
            self._dynamic_scope['value'] = base_scope
            self._dynamic_scope['phase'] = 'idle'
            self._dynamic_scope['last_ms'] = now_ms
        return float(self._dynamic_scope['value'])

    def get_dynamic_aim_scope(self):
        """对外获取当前帧应使用的瞄准范围（像素）。"""
        try:
            return self._update_dynamic_aim_scope()
        except Exception:
            try:
                return float(self.pressed_key_config.get('aim_bot_scope', 0) or 0)
            except Exception:
                return 0.0

    def reset_dynamic_aim_scope(self, for_key=None):
        """当开启动态瞄准范围时，将当前范围重置为该按键的基础范围。\n\n        Args:\n            for_key: 指定按键名称；缺省则使用当前生效按键。\n        """
        try:
            key = for_key or (self.old_pressed_aim_key if self.old_pressed_aim_key else self.select_key)
            key_cfg = self.config['groups'][self.group]['aim_keys'].get(key, self.pressed_key_config)
        except Exception:
            key_cfg = self.pressed_key_config
        dyn_cfg = key_cfg.get('dynamic_scope') or {}
        if not bool(dyn_cfg.get('enabled', False)):
            return
        try:
            base_scope = float(key_cfg.get('aim_bot_scope', 0) or 0)
        except Exception:
            base_scope = 0.0
        self._dynamic_scope['value'] = base_scope
        self._dynamic_scope['phase'] = 'idle'
        self._dynamic_scope['last_ms'] = time.time() * 1000.0

    def save_config_callback(self):
        """异步保存配置回调"""

        def _async_save_callback():
            try:
                result = save_remote_config(self.config)
                if not result:
                    print('保存配置失败，请检查日志文件(config_error.log)获取更多信息')
                    return result
                print('配置保存成功')
                return result
            except Exception as e:
                print(f'配置保存回调异常: {e}')
                return False
        save_thread = threading.Thread(target=_async_save_callback, daemon=True)
        save_thread.start()
        return True

    def _ensure_model_runtime_defaults(self, config):
        return cfgmgr.ensure_model_runtime_defaults(config, get_default_runtime_config)

    def _prepare_v11onnx_group_model(self, group_name, group_val):
        if not should_use_v11onnx(group_val, os.environ):
            return None
        base_config = getattr(self, 'config', None)
        if not isinstance(base_config, dict):
            base_config = {'model_runtime': get_default_runtime_config()}
        runtime_cfg = resolve_runtime_config(base_config, group_val, os.environ)
        search_dirs = runtime_cfg.get('v11_search_dirs', [])
        normalized_search_dirs = []
        if isinstance(search_dirs, list):
            for directory in search_dirs:
                if not isinstance(directory, str):
                    continue
                normalized_search_dirs.append(
                    directory if os.path.isabs(directory) else os.path.join(os.getcwd(), directory)
                )
        configured_path = group_val.get('infer_model')
        if not str(configured_path).lower().endswith('.onnx'):
            configured_path = group_val.get('original_infer_model')
        discovered_path = discover_v11onnx_model(
            configured_path=configured_path,
            search_dirs=normalized_search_dirs if normalized_search_dirs else None,
            env=os.environ,
        )
        if not discovered_path:
            raise ModelValidationError(
                f'未发现可用 v11onnx 模型。请检查 infer_model 或设置环境变量 DOPA_V11ONNX_MODEL。组: {group_name}'
            )
        metadata = validate_v11onnx_model(
            discovered_path,
            expected_opset=runtime_cfg.get('v11_expected_opset'),
            expected_model_version=runtime_cfg.get('v11_expected_model_version'),
            strict_graph=bool(runtime_cfg.get('v11_strict_graph', True)),
        )
        if group_val.get('infer_model') != discovered_path and not (
            group_val.get('is_trt', False) and str(group_val.get('infer_model', '')).lower().endswith('.engine')
        ):
            print(f'[v11onnx] 自动发现模型: {group_val.get("infer_model")} -> {discovered_path}')
            group_val['infer_model'] = discovered_path
        group_val['original_infer_model'] = discovered_path
        group_val['model_variant'] = 'v11onnx'
        # v11onnx 输出布局与 v8 分支保持一致，直接复用现有后处理。
        group_val['is_v8'] = True
        self._model_validation_cache[group_name] = metadata.to_dict()
        print(
            f'[v11onnx] 校验通过: opset={metadata.opset}, '
            f'nodes={metadata.node_count}, outputs={metadata.output_shapes}'
        )
        return metadata


    def _clear_queues(self):
        """清理所有队列，确保切换模型后队列状态正确"""
        try:
            while not self.que_aim.empty():
                try:
                    self.que_aim.get_nowait()
                except Exception:
                    break
            while not self.que_trigger.empty():
                try:
                    self.que_trigger.get_nowait()
                except Exception:
                    return
        except Exception as e:
            print(f'[队列清理] 清理队列时出错: {e}')

    def _reset_aim_states(self):
        """重置自瞄相关状态，确保切换模型后状态正确"""
        try:
            self.old_pressed_aim_key = ''
            self.aim_key_status = False
            self.reset_pid()
            if hasattr(self, 'reset_target_lock'):
                for key in getattr(self, 'aim_key', []):
                    self.reset_target_lock(key)
        except Exception as e:
            print(f'[状态重置] 重置状态时出错: {e}')

    def refresh_engine(self):
        self._clear_queues()
        self._reset_aim_states()
        group_cfg = self.config['groups'][self.group]
        if should_use_v11onnx(group_cfg, os.environ):
            try:
                self._prepare_v11onnx_group_model(self.group, group_cfg)
            except Exception as e:
                print(f'[v11onnx] 刷新引擎前校验失败: {e}')
                self.engine = None
                self.identify_rect_left = 0
                self.identify_rect_top = 0
                return
        runtime_cfg = resolve_runtime_config(self.config, group_cfg, os.environ)
        selected_device = self.config.get('inference_device', 'CPU')
        is_trt = group_cfg.get('is_trt', False)
        model_path = group_cfg['infer_model']
        if self.decrypted_model_data is not None and self.original_model_path == model_path:
            self._create_engine_from_bytes(
                self.decrypted_model_data,
                is_trt=is_trt,
                runtime_cfg=runtime_cfg,
                selected_device=selected_device,
            )
            return
        if model_path.endswith('.ZTX') and self.decrypted_model_data is None:
            self.engine = None
            self.identify_rect_left = 0
            self.identify_rect_top = 0
            return
        if not os.path.exists(model_path):
            print(f'模型文件不存在: {model_path}')
            return
        if is_trt and (not TENSORRT_AVAILABLE):
            is_trt = False
            group_cfg['is_trt'] = False
            if model_path.endswith('.engine'):
                original_path = group_cfg.get('original_infer_model')
                if original_path and os.path.exists(original_path):
                    model_path = original_path
                    group_cfg['infer_model'] = original_path
                else:
                    possible_onnx = os.path.splitext(model_path)[0] + '.onnx'
                    if os.path.exists(possible_onnx):
                        model_path = possible_onnx
                        group_cfg['infer_model'] = possible_onnx
                        group_cfg['original_infer_model'] = possible_onnx
                    else:
                        return None
        self.engine = None
        self._cached_model_area = None
        if model_path.endswith('.engine') and is_trt and TENSORRT_AVAILABLE:
            try:
                self.engine = TensorRTInferenceEngine(model_path)
                print(f'已加载TensorRT .engine 文件: {model_path}')
            except Exception as e:
                print(f'TensorRT引擎加载失败: {e}，尝试切换回原始模型')
                original_path = group_cfg.get('original_infer_model', None)
                if original_path and os.path.exists(original_path):
                    group_cfg['infer_model'] = original_path
                    group_cfg['is_trt'] = False
                    self.refresh_engine()
                    return
                print('未找到原始模型，无法回退')
                return None
        engine_path = os.path.splitext(model_path)[0] + '.engine'
        if (
            self.engine is None
            and is_trt
            and TENSORRT_AVAILABLE
            and (TensorRTInferenceEngine is not None)
            and os.path.exists(engine_path)
        ):
            try:
                self.engine = TensorRTInferenceEngine(engine_path)
                print('已自动切换到 TensorRT .engine 推理。')
            except Exception as e:
                print(f'TensorRT引擎加载失败: {e}，已自动切换为ONNX推理')
                group_cfg['is_trt'] = False
        if self.engine is None:
            if model_path.endswith('data'):
                self.engine = OnnxRuntimeDmlEngine(
                    model_path,
                    is_trt=False,
                    runtime_config=runtime_cfg,
                    selected_device=selected_device,
                    group_config=group_cfg,
                    global_config=self.config,
                )
            else:
                self.engine = OnnxRuntimeDmlEngine(
                    model_path,
                    True,
                    is_trt=False,
                    runtime_config=runtime_cfg,
                    selected_device=selected_device,
                    group_config=group_cfg,
                    global_config=self.config,
                )
        if self.engine is None:
            return
        self.identify_rect_left = self.screen_center_x - self.engine.get_input_shape()[3] / 2
        self.identify_rect_top = self.screen_center_y - self.engine.get_input_shape()[2] / 2
        if isinstance(self.engine, TensorRTInferenceEngine):
            try:
                use_graph = self.config['groups'][self.group].get('use_cuda_graph', True)
            except Exception:
                use_graph = True
            if use_graph and hasattr(self.engine, 'enable_cuda_graph'):
                try:
                    self.engine.enable_cuda_graph()
                except Exception as e:
                    print(f'启用 CUDA Graph 失败: {e}')
            elif hasattr(self.engine, 'disable_cuda_graph'):
                try:
                    self.engine.disable_cuda_graph()
                except Exception as e:
                    note_suppressed('refresh_engine/disable_cuda_graph', e)
                    return

    def _create_engine_from_bytes(self, model_bytes, is_trt=False, runtime_cfg=None, selected_device=None):
        """从字节数据创建推理引擎"""
        try:
            import onnxruntime as rt
            import warnings
            warnings.filterwarnings('ignore', message='.*pagelocked_host_allocation.*')
            warnings.filterwarnings('ignore', message='.*device_allocation.*')
            warnings.filterwarnings('ignore', message='.*stream.*out-of-thread.*')
            warnings.filterwarnings('ignore', message='.*could not be cleaned up.*')
            warnings.filterwarnings('ignore', message='.*stream.*')
            if runtime_cfg is None:
                runtime_cfg = resolve_runtime_config(
                    self.config, self.config.get('groups', {}).get(self.group, {}), os.environ
                )
            if not selected_device:
                selected_device = self.config.get('inference_device', 'CPU')

            providers, provider_options, session_options = build_ort_runtime_components(
                rt_module=rt,
                selected_device=selected_device,
                runtime_cfg=runtime_cfg,
                is_trt=is_trt,
            )
            print(f"推理设备: {selected_device}, 使用的提供者: {providers}")
            session_kwargs = {'providers': providers}
            if provider_options is not None:
                session_kwargs['provider_options'] = provider_options
            if session_options is not None:
                session_kwargs['sess_options'] = session_options
            session = rt.InferenceSession(model_bytes, **session_kwargs)

            class DecryptedModelEngine:
                def __init__(self, session):
                    import threading
                    self.session = session
                    self.input_name = self.session.get_inputs()[0].name
                    self.output_names = [output.name for output in self.session.get_outputs()]
                    self.input_shape = self.session.get_inputs()[0].shape
                    self._lock = threading.Lock()

                def get_input_shape(self):
                    return self.input_shape

                def infer(self, img_input):
                    with self._lock:
                        outputs = self.session.run(self.output_names, {self.input_name: img_input})
                        return outputs

                def get_class_num(self):
                    outputs_meta = self.session.get_outputs()
                    output_shapes = outputs_meta[0].shape
                    return output_shapes[2] - 5

                def get_class_num_v8(self):
                    outputs_meta = self.session.get_outputs()
                    output_shapes = outputs_meta[0].shape
                    return output_shapes[1] - 4

                def __del__(self):
                    """析构函数，确保资源被正确清理"""
                    try:
                        if hasattr(self, 'session'):
                            del self.session
                    except Exception:
                        return None
            self.engine = DecryptedModelEngine(session)
            print('解密模型引擎创建成功')
            self.identify_rect_left = self.screen_center_x - self.engine.get_input_shape()[3] / 2
            self.identify_rect_top = self.screen_center_y - self.engine.get_input_shape()[2] / 2
        except Exception as e:
            print(f'从字节数据创建引擎失败: {e}')
            self.engine = None

