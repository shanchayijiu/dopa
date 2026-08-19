# -*- coding: utf-8 -*-
# CrosshairUIMixin: split from core.py by subsystem refactor.
#准星UI相关回调（dpg控件 / HSV / 取色 / 小目标开关）
import dearpygui.dearpygui as dpg
from aim.crosshair_tracker import CrosshairTracker


class CrosshairUIMixin:
    def _get_crosshair_lock_config(self):
        return self._crosshair_tracker.get_config(self.config)

    def _ensure_crosshair_hsv_ranges(self, cfg):
        CrosshairTracker._ensure_defaults(cfg)
        return cfg

    def _normalize_hsv_value(self, value, min_value, max_value, default_value):
        return CrosshairTracker.normalize_hsv_value(value, min_value, max_value, default_value)

    def _normalize_hsv_range(self, hsv_range):
        return CrosshairTracker.normalize_hsv_range(hsv_range)

    def on_crosshair_lock_enabled_change(self, sender, app_data):
        cfg = self._get_crosshair_lock_config()
        cfg['enabled'] = bool(app_data)
        if not cfg['enabled']:
            self._crosshair_tracker.reset()
        print(f"准星找色: {('启用' if app_data else '禁用')}")

    def on_crosshair_roi_width_change(self, sender, app_data):
        cfg = self._get_crosshair_lock_config()
        cfg['roi_width'] = int(app_data)
        print(f"检测区域宽: {cfg['roi_width']}")

    def on_crosshair_roi_height_change(self, sender, app_data):
        cfg = self._get_crosshair_lock_config()
        cfg['roi_height'] = int(app_data)
        print(f"检测区域高: {cfg['roi_height']}")

    def _get_active_hsv_range(self, cfg=None):
        if cfg is None:
            cfg = self._get_crosshair_lock_config()
        hsv_ranges = cfg.get('hsv_ranges', [])
        if not hsv_ranges:
            hsv_ranges.append({'h_min': 0, 'h_max': 179, 's_min': 0, 's_max': 255, 'v_min': 0, 'v_max': 255})
            cfg['hsv_ranges'] = hsv_ranges
        index = int(cfg.get('active_index', 0))
        if index < 0 or index >= len(hsv_ranges):
            index = 0
            cfg['active_index'] = 0
        hsv_ranges[index] = self._normalize_hsv_range(hsv_ranges[index])
        return hsv_ranges[index], index

    def _set_active_hsv_value(self, key, value):
        if self.crosshair_use_pending and isinstance(self.crosshair_pending_hsv, dict):
            pending = dict(self.crosshair_pending_hsv)
            pending[key] = int(value)
            self.crosshair_pending_hsv = self._normalize_hsv_range(pending)
            self._apply_hsv_to_sliders(self.crosshair_pending_hsv)
            return
        cfg = self._get_crosshair_lock_config()
        hsv_range, index = self._get_active_hsv_range(cfg)
        hsv_range[key] = int(value)
        hsv_range = self._normalize_hsv_range(hsv_range)
        cfg['hsv_ranges'][index] = hsv_range
        self.update_crosshair_hsv_ui(cfg)

    def on_crosshair_h_min_change(self, sender, app_data):
        self._set_active_hsv_value('h_min', app_data)

    def on_crosshair_h_max_change(self, sender, app_data):
        self._set_active_hsv_value('h_max', app_data)

    def on_crosshair_s_min_change(self, sender, app_data):
        self._set_active_hsv_value('s_min', app_data)

    def on_crosshair_s_max_change(self, sender, app_data):
        self._set_active_hsv_value('s_max', app_data)

    def on_crosshair_v_min_change(self, sender, app_data):
        self._set_active_hsv_value('v_min', app_data)

    def on_crosshair_v_max_change(self, sender, app_data):
        self._set_active_hsv_value('v_max', app_data)

    def on_crosshair_color_group_change(self, sender, app_data):
        cfg = self._get_crosshair_lock_config()
        items = self._get_crosshair_color_group_items(cfg)
        if app_data in items:
            cfg['active_index'] = items.index(app_data)
            self.crosshair_use_pending = False
            self.crosshair_pending_hsv = None
            self.crosshair_pending_rgb = None
            self.update_crosshair_hsv_ui(cfg)

    def on_crosshair_show_active_only_change(self, sender, app_data):
        cfg = self._get_crosshair_lock_config()
        cfg['show_active_only'] = bool(app_data)
        print(f"仅预览当前颜色: {('启用' if app_data else '禁用')}")

    def on_crosshair_show_debug_log_change(self, sender, app_data):
        cfg = self._get_crosshair_lock_config()
        cfg['show_debug_log'] = bool(app_data)
        print(f"调试日志: {('启用' if app_data else '禁用')}")

    def on_crosshair_pick_click(self, sender, app_data):
        cfg = self._get_crosshair_lock_config()
        self.crosshair_pick_mode = True
        import dearpygui.dearpygui as dpg
        if self.crosshair_pick_status_text is not None:
            dpg.set_value(self.crosshair_pick_status_text, '取色模式: 等待F3')
        print("进入取色模式，请按F3取色")
    
    def on_crosshair_start_click(self, sender, app_data):
        cfg = self._get_crosshair_lock_config()
        if not cfg.get('enabled', False):
            cfg['enabled'] = True
            import dearpygui.dearpygui as dpg
            if self.crosshair_lock_enabled_checkbox is not None:
                dpg.set_value(self.crosshair_lock_enabled_checkbox, True)
            print("准星找色: 启用")

    def on_crosshair_h_tolerance_change(self, sender, app_data):
        cfg = self._get_crosshair_lock_config()
        cfg['h_tolerance'] = int(app_data)
        print(f"H容差: {cfg['h_tolerance']}")

    def on_crosshair_s_tolerance_change(self, sender, app_data):
        cfg = self._get_crosshair_lock_config()
        cfg['s_tolerance'] = int(app_data)
        print(f"S容差: {cfg['s_tolerance']}")

    def on_crosshair_v_tolerance_change(self, sender, app_data):
        cfg = self._get_crosshair_lock_config()
        cfg['v_tolerance'] = int(app_data)
        print(f"V容差: {cfg['v_tolerance']}")

    def on_crosshair_min_area_change(self, sender, app_data):
        cfg = self._get_crosshair_lock_config()
        cfg['min_area'] = float(app_data)
        print(f"最小识别面积: {cfg['min_area']}")

    def on_crosshair_delete_color_click(self, sender, app_data):
        cfg = self._get_crosshair_lock_config()
        hsv_ranges = cfg.get('hsv_ranges', [])
        if len(hsv_ranges) <= 1:
            return
        index = int(cfg.get('active_index', 0))
        if index < 0 or index >= len(hsv_ranges):
            index = 0
        hsv_ranges.pop(index)
        if index >= len(hsv_ranges):
            index = len(hsv_ranges) - 1
        cfg['active_index'] = max(0, index)
        cfg['hsv_ranges'] = hsv_ranges
        self.crosshair_use_pending = False
        self.crosshair_pending_hsv = None
        self.crosshair_pending_rgb = None
        self.update_crosshair_hsv_ui(cfg)

    def handle_color_pick_hotkey(self):
        if not self.crosshair_pick_mode:
            return
        
        frame = self.screenshot_manager.get_screenshot((0, 0, self.screen_width, self.screen_height))
        if frame is None:
            frame = self._crosshair_tracker.last_frame
            print("警告: 实时截图失败，使用缓存帧")
        if frame is None:
            print("错误: 无法获取画面进行取色")
            return

        cfg = self._get_crosshair_lock_config()
        result = self._crosshair_tracker.pick_color(frame, cfg)
        if result is None:
            return

        new_range, (r, g, b), (h_val, s_val, v_val) = result
        print(f"取色区域: 对比背景自动分离准星像素, 取色值: BGR=[{b},{g},{r}], HSV=[{h_val},{s_val},{v_val}]")

        cfg['hsv_ranges'].append(new_range)
        cfg['active_index'] = len(cfg['hsv_ranges']) - 1
        cfg['last_rgb'] = [r, g, b]
        
        self.crosshair_pick_mode = False
        import dearpygui.dearpygui as dpg
        if self.crosshair_pick_status_text is not None:
            dpg.set_value(self.crosshair_pick_status_text, '取色完成')
        
        self.update_crosshair_hsv_ui(cfg)
        print(f"取色完成: HSV=[{h_val}, {s_val}, {v_val}], RGB=[{r}, {g}, {b}]")

    def _format_rgb_text(self, rgb):
        if not isinstance(rgb, (list, tuple)) or len(rgb) < 3:
            return 'RGB: -'
        r, g, b = [int(v) for v in rgb[:3]]
        return f'RGB: {r},{g},{b}'

    def _get_crosshair_color_group_items(self, cfg=None):
        if cfg is None:
            cfg = self._get_crosshair_lock_config()
        hsv_ranges = cfg.get('hsv_ranges', [])
        return [f'颜色{index + 1}' for index in range(len(hsv_ranges))]

    def _apply_hsv_to_sliders(self, hsv_range):
        import dearpygui.dearpygui as dpg
        if not isinstance(hsv_range, dict):
            return
        if self.crosshair_h_min_slider is not None:
            dpg.set_value(self.crosshair_h_min_slider, int(hsv_range.get('h_min', 0)))
        if self.crosshair_h_max_slider is not None:
            dpg.set_value(self.crosshair_h_max_slider, int(hsv_range.get('h_max', 179)))
        if self.crosshair_s_min_slider is not None:
            dpg.set_value(self.crosshair_s_min_slider, int(hsv_range.get('s_min', 0)))
        if self.crosshair_s_max_slider is not None:
            dpg.set_value(self.crosshair_s_max_slider, int(hsv_range.get('s_max', 255)))
        if self.crosshair_v_min_slider is not None:
            dpg.set_value(self.crosshair_v_min_slider, int(hsv_range.get('v_min', 0)))
        if self.crosshair_v_max_slider is not None:
            dpg.set_value(self.crosshair_v_max_slider, int(hsv_range.get('v_max', 255)))

    def update_crosshair_hsv_ui(self, cfg=None):
        if cfg is None:
            cfg = self._get_crosshair_lock_config()
        hsv_range, index = self._get_active_hsv_range(cfg)
        import dearpygui.dearpygui as dpg
        if self.crosshair_h_min_slider is not None:
            dpg.set_value(self.crosshair_h_min_slider, int(hsv_range.get('h_min', 0)))
        if self.crosshair_h_max_slider is not None:
            dpg.set_value(self.crosshair_h_max_slider, int(hsv_range.get('h_max', 179)))
        if self.crosshair_s_min_slider is not None:
            dpg.set_value(self.crosshair_s_min_slider, int(hsv_range.get('s_min', 0)))
        if self.crosshair_s_max_slider is not None:
            dpg.set_value(self.crosshair_s_max_slider, int(hsv_range.get('s_max', 255)))
        if self.crosshair_v_min_slider is not None:
            dpg.set_value(self.crosshair_v_min_slider, int(hsv_range.get('v_min', 0)))
        if self.crosshair_v_max_slider is not None:
            dpg.set_value(self.crosshair_v_max_slider, int(hsv_range.get('v_max', 255)))
        if self.crosshair_color_group_combo is not None:
            items = self._get_crosshair_color_group_items(cfg)
            dpg.configure_item(self.crosshair_color_group_combo, items=items)
            if items:
                dpg.set_value(self.crosshair_color_group_combo, items[index])
        if self.crosshair_rgb_text is not None:
            dpg.set_value(self.crosshair_rgb_text, self._format_rgb_text(cfg.get('last_rgb', [0, 0, 0])))

    def on_crosshair_show_crosshair_change(self, sender, app_data):
        cfg = self._get_crosshair_lock_config()
        cfg['show_crosshair'] = bool(app_data)

    def on_crosshair_show_lock_box_change(self, sender, app_data):
        cfg = self._get_crosshair_lock_config()
        cfg['show_lock_box'] = bool(app_data)

    def on_crosshair_only_when_aiming_change(self, sender, app_data):
        cfg = self._get_crosshair_lock_config()
        cfg['only_when_aiming'] = bool(app_data)
        print(f"仅瞄准时启用: {('启用' if app_data else '禁用')}")

    def on_crosshair_max_area_change(self, sender, app_data):
        cfg = self._get_crosshair_lock_config()
        cfg['max_area'] = float(app_data)
        print(f"最大识别面积: {cfg['max_area']}")
        
    def on_crosshair_show_mask_change(self, sender, app_data):
        cfg = self._get_crosshair_lock_config()
        cfg['show_mask'] = bool(app_data)
        print(f"显示过滤效果: {('启用' if app_data else '禁用')}")

    def on_pull_k_change(self, sender, app_data):
        cfg = self._get_crosshair_lock_config()
        cfg['pull_k'] = float(app_data)
        print(f"回拉强度: {cfg['pull_k']}")

    def on_pull_max_speed_change(self, sender, app_data):
        cfg = self._get_crosshair_lock_config()
        cfg['pull_max_speed'] = float(app_data)
        print(f"最大速度: {cfg['pull_max_speed']}")

    def on_pull_deadzone_change(self, sender, app_data):
        cfg = self._get_crosshair_lock_config()
        cfg['pull_deadzone'] = float(app_data)
        print(f"回拉死区: {cfg['pull_deadzone']}")

    def on_ema_smooth_change(self, sender, app_data):
        cfg = self._get_crosshair_lock_config()
        cfg['ema_smooth'] = float(app_data)
        print(f"平滑系数: {cfg['ema_smooth']}")

    def on_small_pixel_threshold_change(self, sender, app_data):
        cfg = self._get_crosshair_lock_config()
        cfg['small_pixel_threshold'] = int(app_data)
        print(f"小目标阈值: {cfg['small_pixel_threshold']}")

    def on_small_target_enabled_change(self, sender, app_data):
        self.config['small_target_enhancement']['enabled'] = app_data
        print(f"小目标识别增强: {('启用' if app_data else '禁用')}")

    def on_small_target_smooth_change(self, sender, app_data):
        self.config['small_target_enhancement']['smooth_enabled'] = app_data
        print(f"小目标平滑: {('启用' if app_data else '禁用')}")

    def on_small_target_nms_change(self, sender, app_data):
        self.config['small_target_enhancement']['adaptive_nms'] = app_data
        print(f"自适应NMS: {('启用' if app_data else '禁用')}")

    def on_small_target_boost_change(self, sender, app_data):
        self.config['small_target_enhancement']['boost_factor'] = app_data
        print(f'小目标增强倍数设置为: {app_data}')

    def on_small_target_frames_change(self, sender, app_data):
        self.config['small_target_enhancement']['smooth_frames'] = app_data
        self.target_history_max_frames = app_data
        print(f'平滑历史帧数设置为: {app_data}')

    def on_small_target_threshold_change(self, sender, app_data):
        self.config['small_target_enhancement']['threshold'] = app_data
        print(f'小目标阈值设置为: {app_data:.3f}')

    def on_medium_target_threshold_change(self, sender, app_data):
        self.config['small_target_enhancement']['medium_threshold'] = app_data
        print(f'中等目标阈值设置为: {app_data:.3f}')
