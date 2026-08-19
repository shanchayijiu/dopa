# -*- coding: utf-8 -*-
"""配置管理 Mixin — 从 core.py 提取。

包含配置构建(build_config)、配置迁移(migrate_config_to_class_based)、
按键配置刷新(refresh_pressed_key_config)、控制器参数刷新(refresh_controller_params)、
配置变更处理器初始化(_init_config_handlers)。
所有方法操作 self.* 属性，由 Valorant.__init__ 创建，通过 mix-in 继承可用。
"""
import os
import copy
import random
from settings import config_manager as cfgmgr
from util.gui_handlers import ConfigItemGroup, ConfigChangeHandler
from inference.v11onnx_support import should_use_v11onnx
from inference.v11onnx_support import should_use_v11onnx, infer_model_variant_from_path
from ..runtime import TENSORRT_AVAILABLE


class ConfigMixin:
    """配置管理 Mixin。"""

    def build_config(self):
        """\n        构建配置并返回相关参数\n        \n        处理TRT相关路径设置并获取当前组的按键配置\n        \n        Returns:\n            tuple: (config, aim_keys_dist, aim_keys, group) 配置字典、按键配置字典、按键列表和当前组名\n        """
        if hasattr(self, 'config') and self.config:
            config = self.config
        else:
            # 跳过远程配置验证，直接读取本地cfg.json
            print('跳过远程配置验证，直接读取本地cfg.json')
            config = self.read_local_cfg()
            if config is None:
                print('cfg.json文件不存在，使用默认配置')
                config = self.get_default_config()
        cfgmgr.ensure_defaults(config)
        self._ensure_model_runtime_defaults(config)
        if 'crosshair_color_lock' in config:
            crosshair_cfg = config['crosshair_color_lock']
            if not isinstance(crosshair_cfg, dict):
                crosshair_cfg = {}
                config['crosshair_color_lock'] = crosshair_cfg
            crosshair_cfg = self._ensure_crosshair_hsv_ranges(crosshair_cfg)
        for group_key, group_val in config.get('groups', {}).items():
            if 'is_trt' not in group_val:
                group_val['is_trt'] = False
            if 'is_v8' not in group_val:
                group_val['is_v8'] = False
            current_model = group_val.get('infer_model', '')
            if 'model_variant' not in group_val:
                group_val['model_variant'] = infer_model_variant_from_path(
                    current_model, bool(group_val.get('is_v8', False))
                )
            env_variant = str(os.environ.get('DOPA_MODEL_VARIANT', '') or '').strip().lower()
            if env_variant in {'v11', 'v11onnx', 'yolov11', 'yolo11'}:
                group_val['model_variant'] = 'v11onnx'
            if 'infer_model' not in group_val:
                continue
            current_model = group_val['infer_model']
            if 'original_infer_model' not in group_val:
                if current_model.endswith('.engine'):
                    onnx_path = os.path.splitext(current_model)[0] + '.onnx'
                    if os.path.exists(onnx_path):
                        group_val['original_infer_model'] = onnx_path
                elif current_model.endswith('.onnx'):
                    group_val['original_infer_model'] = current_model
                elif current_model.endswith('.ZTX'):
                    group_val['original_infer_model'] = current_model
            if group_val.get('is_trt', False):
                if not TENSORRT_AVAILABLE:
                    print(f'组 {group_key} 已设置使用TRT，但TensorRT环境不可用，自动切换为原始模式')
                    group_val['is_trt'] = False
                    original_path = group_val.get('original_infer_model', group_val['infer_model'])
                    if original_path.endswith('.ZTX'):
                        if original_path!= group_val['infer_model'] and os.path.exists(original_path):
                            group_val['infer_model'] = original_path
                    elif original_path!= group_val['infer_model'] and os.path.exists(original_path):
                        group_val['infer_model'] = original_path
                        print(f'已自动切回ONNX模式: {original_path}')
                else:
                    original_path = group_val.get('original_infer_model', group_val['infer_model'])
                    if original_path.endswith('.ZTX'):
                        engine_path = os.path.splitext(original_path)[0] + '.engine'
                        if os.path.exists(engine_path):
                            group_val['infer_model'] = engine_path
                        elif original_path!= group_val['infer_model'] and os.path.exists(original_path):
                            group_val['infer_model'] = original_path
                    else:
                        engine_path = os.path.splitext(original_path)[0] + '.engine'
                        if os.path.exists(engine_path):
                            group_val['infer_model'] = engine_path
                        else:
                            print(f'警告: TRT引擎文件不存在: {engine_path}')
                            if original_path!= group_val['infer_model'] and os.path.exists(original_path):
                                group_val['infer_model'] = original_path
                                group_val['is_trt'] = False
                                print(f'已自动切回ONNX模式: {original_path}')
                            continue
            else:
                original_path = group_val.get('original_infer_model', group_val['infer_model'])
                if original_path.endswith('.ZTX'):
                    continue
                if os.path.exists(original_path):
                    group_val['infer_model'] = original_path
            if should_use_v11onnx(group_val, os.environ):
                try:
                    self._prepare_v11onnx_group_model(group_key, group_val)
                except Exception as e:
                    print(f'[v11onnx] 组 {group_key} 预检查失败: {e}')
        # 设置默认组
        group = config.get('group', 'default')
        config['group'] = group
        
        if group and group in config['groups']:
            # 确保组配置中有aim_keys
            if 'aim_keys' not in config['groups'][group]:
                config['groups'][group]['aim_keys'] = {}
            aim_keys_dist = config['groups'][group]['aim_keys']
            aim_keys = list(aim_keys_dist.keys())
            self.migrate_config_to_class_based(config)
            self.init_all_keys_class_aim_positions(group, config)
        else:
            aim_keys_dist = {}
            aim_keys = []
        return (config, aim_keys_dist, aim_keys, group)

    def init_all_keys_class_aim_positions(self, group, config):
        """为所有按键初始化类别瞄准位置配置"""
        try:
            old_group = getattr(self, 'group', None)
            self.group = group
            self.config = config
            class_num = self.get_current_class_num()
            for key_name in config['groups'][group]['aim_keys']:
                key_config = config['groups'][group]['aim_keys'][key_name]
                if 'class_aim_positions' not in key_config:
                    key_config['class_aim_positions'] = {}
                cap = key_config['class_aim_positions']
                if isinstance(cap, list):
                    converted = {}
                    for idx, item in enumerate(cap):
                        if isinstance(item, dict):
                            converted[str(idx)] = {'aim_bot_position': float(item.get('aim_bot_position', 0.0)), 'aim_bot_position2': float(item.get('aim_bot_position2', 0.0)), 'confidence_threshold': float(item.get('confidence_threshold', 0.5)), 'iou_t': float(item.get('iou_t', 1.0))}
                        else:
                            converted[str(idx)] = {'aim_bot_position': 0.0, 'aim_bot_position2': 0.0, 'confidence_threshold': 0.5, 'iou_t': 1.0}
                    key_config['class_aim_positions'] = converted
                elif not isinstance(cap, dict):
                    key_config['class_aim_positions'] = {}
                if 'class_priority_order' not in key_config:
                    key_config['class_priority_order'] = list(range(class_num))
                if 'overshoot_threshold' not in key_config:
                    key_config['overshoot_threshold'] = 3.0
                if 'overshoot_x_factor' not in key_config:
                    key_config['overshoot_x_factor'] = 0.5
                if 'overshoot_y_factor' not in key_config:
                    key_config['overshoot_y_factor'] = 0.3
                for i in range(class_num):
                    class_str = str(i)
                    if class_str not in key_config['class_aim_positions']:
                        key_config['class_aim_positions'][class_str] = {'aim_bot_position': 0.0, 'aim_bot_position2': 0.0, 'confidence_threshold': 0.5, 'iou_t': 1.0}
            if old_group is not None:
                self.group = old_group
        except Exception as e:
            print(f'初始化所有按键的类别瞄准配置失败: {e}')
            import traceback
            traceback.print_exc()

    def migrate_config_to_class_based(self, config):
        cfgmgr.migrate_to_class_based(config)

    def calculate_max_pixel_distance(self, screen_width, screen_height, fov_angle):
        diagonal_distance = (screen_width ** 2 + screen_height ** 2) ** 0.5
        max_pixel_distance = diagonal_distance / 2 * (fov_angle / 180)
        return max_pixel_distance

    def refresh_controller_params(self):
        self.aim_pid.set_pid_params(kp=[self.pressed_key_config.get('pid_kp_x', 0.4), self.pressed_key_config.get('pid_kp_y', 0.4)], ki=[self.pressed_key_config.get('pid_ki_x', 0.02), self.pressed_key_config.get('pid_ki_y', 0.02)], kd=[self.pressed_key_config.get('pid_kd_x', 0.002), self.pressed_key_config.get('pid_kd_y', 0)])
        integral_limit_x = self.pressed_key_config.get('pid_integral_limit_x', 0.0)
        integral_limit_y = self.pressed_key_config.get('pid_integral_limit_y', 0.0)
        self.aim_pid.set_windup_guard([integral_limit_x, integral_limit_y])
        smooth_x = self.pressed_key_config.get('smooth_x', 0)
        smooth_y = self.pressed_key_config.get('smooth_y', 0)
        smooth_deadzone = self.pressed_key_config.get('smooth_deadzone', 0.0)
        smooth_algorithm = self.pressed_key_config.get('smooth_algorithm', 1.0)
        self.aim_pid.set_smooth_params(smooth_x, smooth_y, smooth_deadzone, smooth_algorithm)
        self.aim_pid.set_error_filter(
            alpha=self.pressed_key_config.get('pid_error_filter_alpha', 0.0),
        )
        self.aim_pid.set_vel_filter(
            alpha=self.pressed_key_config.get('pid_vel_filter_alpha', 0.0),
        )
        # 同步 tracker 参数
        if hasattr(self, 'aim_pipeline') and self.aim_pipeline is not None:
            self.aim_pipeline.tracker_enabled = bool(self.pressed_key_config.get('tracker_enabled', True))
            try:
                self.aim_pipeline.tracker.match_thresh = float(self.pressed_key_config.get('tracker_match_thresh', 0.3))
            except Exception as e:
                print(f'tracker match_thresh同步失败: {e}')
            try:
                self.aim_pipeline.tracker.track_buffer = int(self.pressed_key_config.get('tracker_track_buffer', 30))
            except Exception as e:
                print(f'tracker track_buffer同步失败: {e}')
            # 同步移动预测 & ID锁定参数
            kalman_cfg = self.config.get('kalman', {})
            self.aim_pipeline.kalman_enabled = bool(kalman_cfg.get('enabled', True))
            self.aim_pipeline.kalman_predict_frames = int(kalman_cfg.get('predict_frames', 5))
            self.aim_pipeline.target_id_lock_enabled = bool(self.config.get('target_id_lock_enabled', True))

    def refresh_pressed_key_config(self, key):
        """\n        刷新当前按下按键的配置\n        \n        Args:\n            key: 按键名称\n        """
        if key!= self.old_refreshed_aim_key:
            if key not in self.aim_keys_dist:
                return
            self.old_refreshed_aim_key = key
            self.pressed_key_config = self.aim_keys_dist[key]
            if hasattr(self, 'aim_pid'):
                self.aim_pid.reset()
            self.refresh_controller_params()

    def get_aim_position_for_class(self, class_id):
        """根据类别ID获取瞄准位置"""
        if 'class_aim_positions' not in self.pressed_key_config:
            return random.uniform(self.pressed_key_config.get('aim_bot_position', 0.5), self.pressed_key_config.get('aim_bot_position2', 0.5))
        class_str = str(class_id)
        if class_str in self.pressed_key_config['class_aim_positions']:
            config = self.pressed_key_config['class_aim_positions'][class_str]
            return random.uniform(config['aim_bot_position'], config['aim_bot_position2'])
        return random.uniform(self.pressed_key_config.get('aim_bot_position', 0.5), self.pressed_key_config.get('aim_bot_position2', 0.5))


    def _init_config_handlers(self):
        """\n        初始化配置变更处理器，注册配置项和处理函数\n        """
        basic_group = ConfigItemGroup(self.config_handler)
        basic_group.register_item('card', 'card', str)
        basic_group.register_item('infer_debug', 'infer_debug', bool)
        basic_group.register_item('is_curve', 'is_curve', bool)
        basic_group.register_item('is_curve_uniform', 'is_curve_uniform', bool)
        basic_group.register_item('print_fps', 'print_fps', bool)
        basic_group.register_item('show_motion_speed', 'show_motion_speed', bool, self.refresh_controller_params)
        basic_group.register_item('is_show_curve', 'is_show_curve', bool)
        basic_group.register_item('is_show_down', 'is_show_down', bool)
        basic_group.register_item('game_sensitivity', 'game_sensitivity', float)
        basic_group.register_item('mouse_dpi', 'mouse_dpi', int)
        basic_group.register_item('is_v8', 'is_v8', bool)
        basic_group.register_item('right_down', 'right_down', bool)
        scoring_group = ConfigItemGroup(self.config_handler)
        scoring_group.register_item('target_sticky_pixels', 'target_sticky_pixels', float)
        scoring_group.register_item('target_lock_ms', 'target_lock_ms', float)
        screenshot_group = ConfigItemGroup(self.config_handler)
        screenshot_group.register_item('is_obs', 'is_obs', bool, lambda: self.screenshot_manager.update_config('is_obs', self.config['is_obs']) if self.screenshot_manager else None)
        screenshot_group.register_item('is_cjk', 'is_cjk', bool, lambda: self.screenshot_manager.update_config('is_cjk', self.config['is_cjk']) if self.screenshot_manager else None)
        screenshot_group.register_item('obs_ip', 'obs_ip', str, lambda: self.screenshot_manager.update_config('obs_ip', self.config['obs_ip']) if self.screenshot_manager else None)
        screenshot_group.register_item('obs_port', 'obs_port', int, lambda: self.screenshot_manager.update_config('obs_port', self.config['obs_port']) if self.screenshot_manager else None)
        screenshot_group.register_item('obs_fps', 'obs_fps', int, lambda: self.screenshot_manager.update_config('obs_fps', self.config['obs_fps']) if self.screenshot_manager else None)
        screenshot_group.register_item('cjk_device_id', 'cjk_device_id', int, lambda: self.screenshot_manager.update_config('cjk_device_id', self.config['cjk_device_id']) if self.screenshot_manager else None)
        screenshot_group.register_item('cjk_fps', 'cjk_fps', int, lambda: self.screenshot_manager.update_config('cjk_fps', self.config['cjk_fps']) if self.screenshot_manager else None)
        screenshot_group.register_item('cjk_resolution', 'cjk_resolution', int, lambda: self.screenshot_manager.update_config('cjk_resolution', self.config['cjk_resolution']) if self.screenshot_manager else None)
        screenshot_group.register_item('cjk_crop_size', 'cjk_crop_size', int, lambda: self.screenshot_manager.update_config('cjk_crop_size', self.config['cjk_crop_size']) if self.screenshot_manager else None)
        screenshot_group.register_item('enable_parallel_processing', 'enable_parallel_processing', bool, lambda: self.screenshot_manager.update_config('enable_parallel_processing', self.config['enable_parallel_processing']) if self.screenshot_manager else None)
        screenshot_group.register_item('turbo_mode', 'turbo_mode', bool, lambda: self.screenshot_manager.update_config('turbo_mode', self.config['turbo_mode']) if self.screenshot_manager else None)
        screenshot_group.register_item('skip_frame_processing', 'skip_frame_processing', bool, lambda: self.screenshot_manager.update_config('skip_frame_processing', self.config['skip_frame_processing']) if self.screenshot_manager else None)
        curve_group = ConfigItemGroup(self.config_handler)
        curve_group.register_item('offset_boundary_x', 'offset_boundary_x', int)
        curve_group.register_item('offset_boundary_y', 'offset_boundary_y', int)
        curve_group.register_item('knots_count', 'knots_count', int)
        curve_group.register_item('distortion_mean', 'distortion_mean', float)
        curve_group.register_item('distortion_st_dev', 'distortion_st_dev', float)
        curve_group.register_item('distortion_frequency', 'distortion_frequency', float)
        curve_group.register_item('target_points', 'target_points', int)
        move_group = ConfigItemGroup(self.config_handler)
        move_group.register_item('km_box_vid', 'km_box_vid', str)
        move_group.register_item('km_box_pid', 'km_box_pid', str)
        move_group.register_item('km_net_ip', 'km_net_ip', str)
        move_group.register_item('km_net_port', 'km_net_port', int)
        move_group.register_item('km_net_uuid', 'km_net_uuid', str)
        move_group.register_item('dhz_ip', 'dhz_ip', str)
        move_group.register_item('dhz_port', 'dhz_port', int)
        move_group.register_item('dhz_random', 'dhz_random', bool)
        move_group.register_item('km_com', 'km_com', str)
        move_group.register_item('move_method', 'move_method', str)
        key_group = ConfigItemGroup(self.config_handler)
        key_group.register_item('group', 'group', str, self.update_group_inputs)
        aim_key_group = ConfigItemGroup(self.config_handler, 'groups.{group}.aim_keys.{key}')
        aim_key_group.register_item('confidence_threshold', 'confidence_threshold', float)
        aim_key_group.register_item('iou_t', 'iou_t', float)
        aim_key_group.register_item('aim_bot_position', 'aim_bot_position', float)
        aim_key_group.register_item('aim_bot_position2', 'aim_bot_position2', float)
        aim_key_group.register_item('aim_bot_scope', 'aim_bot_scope', int)
        aim_key_group.register_item('min_position_offset', 'min_position_offset', int)
        aim_key_group.register_item('smoothing_factor', 'smoothing_factor', float, self.refresh_controller_params)
        aim_key_group.register_item('base_step', 'base_step', float, self.refresh_controller_params)
        aim_key_group.register_item('distance_weight', 'distance_weight', float, self.refresh_controller_params)
        aim_key_group.register_item('fov_angle', 'fov_angle', float, self.refresh_controller_params)
        aim_key_group.register_item('history_size', 'history_size', float, self.refresh_controller_params)
        aim_key_group.register_item('deadzone', 'deadzone', float, self.refresh_controller_params)
        aim_key_group.register_item('smoothing', 'smoothing', float, self.refresh_controller_params)
        aim_key_group.register_item('velocity_decay', 'velocity_decay', float, self.refresh_controller_params)
        aim_key_group.register_item('current_frame_weight', 'current_frame_weight', float, self.refresh_controller_params)
        aim_key_group.register_item('last_frame_weight', 'last_frame_weight', float, self.refresh_controller_params)
        aim_key_group.register_item('output_scale_x', 'output_scale_x', float, self.refresh_controller_params)
        aim_key_group.register_item('output_scale_y', 'output_scale_y', float, self.refresh_controller_params)
        aim_key_group.register_item('uniform_threshold', 'uniform_threshold', float)
        aim_key_group.register_item('min_velocity_threshold', 'min_velocity_threshold', float)
        aim_key_group.register_item('max_velocity_threshold', 'max_velocity_threshold', float)
        aim_key_group.register_item('compensation_factor', 'compensation_factor', float)
        aim_key_group.register_item('auto_y', 'auto_y', bool)
        aim_key_group.register_item('use_crosshair', 'use_crosshair', bool)
        aim_key_group.register_item('pid_kp_x', 'pid_kp_x', float, self.refresh_controller_params)
        aim_key_group.register_item('pid_ki_x', 'pid_ki_x', float, self.refresh_controller_params)
        aim_key_group.register_item('pid_kd_x', 'pid_kd_x', float, self.refresh_controller_params)
        aim_key_group.register_item('pid_kp_y', 'pid_kp_y', float, self.refresh_controller_params)
        aim_key_group.register_item('pid_ki_y', 'pid_ki_y', float, self.refresh_controller_params)
        aim_key_group.register_item('pid_kd_y', 'pid_kd_y', float, self.refresh_controller_params)
        aim_key_group.register_item('pid_integral_limit_x', 'pid_integral_limit_x', float, self.refresh_controller_params)
        aim_key_group.register_item('pid_integral_limit_y', 'pid_integral_limit_y', float, self.refresh_controller_params)
        aim_key_group.register_item('smooth_x', 'smooth_x', float, self.refresh_controller_params)
        aim_key_group.register_item('smooth_y', 'smooth_y', float, self.refresh_controller_params)
        aim_key_group.register_item('smooth_deadzone', 'smooth_deadzone', float, self.refresh_controller_params)
        aim_key_group.register_item('smooth_algorithm', 'smooth_algorithm', float, self.refresh_controller_params)
        aim_key_group.register_item('move_deadzone', 'move_deadzone', float)
        aim_key_group.register_item('pid_error_filter_alpha', 'pid_error_filter_alpha', float, self.refresh_controller_params)
        aim_key_group.register_item('pid_vel_filter_alpha', 'pid_vel_filter_alpha', float, self.refresh_controller_params)
        aim_key_group.register_item('tracker_enabled', 'tracker_enabled', bool, self.refresh_controller_params)
        aim_key_group.register_item('tracker_match_thresh', 'tracker_match_thresh', float, self.refresh_controller_params)
        aim_key_group.register_item('tracker_track_buffer', 'tracker_track_buffer', int, self.refresh_controller_params)
        aim_key_group.register_item('target_switch_delay', 'target_switch_delay', int)
        aim_key_group.register_item('target_reference_class', 'target_reference_class', int)
        aim_key_group.register_item('dynamic_scope.enabled', 'dynamic_scope.enabled', bool)
        aim_key_group.register_item('dynamic_scope.min_ratio', 'dynamic_scope.min_ratio', float)
        aim_key_group.register_item('dynamic_scope.min_scope', 'dynamic_scope.min_scope', int)
        aim_key_group.register_item('dynamic_scope.shrink_duration_ms', 'dynamic_scope.shrink_duration_ms', int)
        aim_key_group.register_item('dynamic_scope.recover_duration_ms', 'dynamic_scope.recover_duration_ms', int)
        aim_key_group.register_item('status', 'status', bool)
        aim_key_group.register_item('start_delay', 'start_delay', float)
        aim_key_group.register_item('long_press_duration', 'long_press_duration', int)
        aim_key_group.register_item('press_delay', 'press_delay', float)
        aim_key_group.register_item('end_delay', 'end_delay', float)
        aim_key_group.register_item('random_delay', 'random_delay', float)
        aim_key_group.register_item('x_trigger_scope', 'x_trigger_scope', int)
        aim_key_group.register_item('y_trigger_scope', 'y_trigger_scope', int)
        aim_key_group.register_item('x_trigger_offset', 'x_trigger_offset', int)
        aim_key_group.register_item('y_trigger_offset', 'y_trigger_offset', int)
        infer_group = ConfigItemGroup(self.config_handler)
        infer_group.register_item('is_trt', 'is_trt', bool, None, self.on_is_trt_change)
        infer_group.register_item('show_infer_time', 'show_infer_time', bool)
        mask_group = ConfigItemGroup(self.config_handler)
        mask_group.register_item('mask_left', 'mask_left', bool, None, self.on_mask_left_change)
        mask_group.register_item('mask_right', 'mask_right', bool, None, self.on_mask_right_change)
        mask_group.register_item('mask_middle', 'mask_middle', bool, None, self.on_mask_middle_change)
        mask_group.register_item('mask_side1', 'mask_side1', bool, None, self.on_mask_side1_change)
        mask_group.register_item('mask_side2', 'mask_side2', bool, None, self.on_mask_side2_change)
        mask_group.register_item('mask_x', 'mask_x', bool, None, self.on_mask_x_change)
        mask_group.register_item('mask_y', 'mask_y', bool, None, self.on_mask_y_change)
        mask_group.register_item('mask_wheel', 'mask_wheel', bool, None, self.on_mask_wheel_change)
        mask_group.register_item('aim_mask_x', 'aim_mask_x', int)
        mask_group.register_item('aim_mask_y', 'aim_mask_y', int)
        self.config_handler.register_config_item('infer_model', 'groups.{group}.infer_model', None, None, self.on_infer_model_change)
        self.config_handler.register_config_item('key', 'key', None, None, self.on_key_change)
        self.config_handler.register_config_item('games', 'games', None, None, self.on_games_change)
        self.config_handler.register_config_item('guns', 'guns', None, None, self.on_guns_change)
        self.config_handler.register_config_item('stages', 'stages', None, None, self.on_stages_change)

