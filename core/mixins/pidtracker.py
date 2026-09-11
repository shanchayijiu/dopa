# -*- coding: utf-8 -*-
"""PID/跟踪器配置 Mixin - 从 core.py 抽取的 PID/平滑/跟踪/卡尔曼配置回调与辅助方法。

包括：on_controller_type/pid_(kp/ki/kd)_(x/y)/pid_integral_limit_(x/y)/
smooth_(x/y)/smooth_deadzone/smooth_algorithm/move_deadzone/
pid_error_filter_alpha/pid_vel_filter_alpha/tracker_enabled/tracker_match_thresh/
tracker_track_buffer/target_id_lock/kalman_enabled/kalman_predict_frames/
target_switch_delay/target_reference_class_change。
另含 _update_pid_params（PID 回调内部刷参数）、_register_control_callback（为控件注册 self.on_change 回调）。
"""
import dearpygui.dearpygui as dpg


class PidTrackerMixin:
    """PID/跟踪器配置回调 Mixin。

    依赖 Valorant 提供:
      self.config / self.group / self.select_key
      self.refresh_controller_params() (core)
      self.on_change (core 通用分发器) - 仅 _register_control_callback 引用
    """

    def on_controller_type_change(self, sender, app_data):
        """控制器类型切换"""
        print('当前版本只支持PID控制器')

    def on_pid_kp_x_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['pid_kp_x'] = round(app_data, 4)
        self._update_pid_params()

    def on_pid_ki_x_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['pid_ki_x'] = round(app_data, 4)
        self._update_pid_params()

    def on_pid_kd_x_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['pid_kd_x'] = round(app_data, 4)
        self._update_pid_params()

    def on_pid_kp_y_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['pid_kp_y'] = round(app_data, 4)
        self._update_pid_params()

    def on_pid_ki_y_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['pid_ki_y'] = round(app_data, 4)
        self._update_pid_params()

    def on_pid_kd_y_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['pid_kd_y'] = round(app_data, 4)
        self._update_pid_params()

    def on_pid_integral_limit_x_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['pid_integral_limit_x'] = round(app_data, 4)
        self._update_pid_params()

    def on_pid_integral_limit_y_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['pid_integral_limit_y'] = round(app_data, 4)
        self._update_pid_params()

    def on_smooth_x_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['smooth_x'] = round(app_data, 4)
        self._update_pid_params()

    def on_smooth_y_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['smooth_y'] = round(app_data, 4)
        self._update_pid_params()

    def on_smooth_deadzone_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['smooth_deadzone'] = round(app_data, 4)
        self._update_pid_params()

    def on_smooth_algorithm_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['smooth_algorithm'] = round(app_data, 4)
        self._update_pid_params()

    def on_move_deadzone_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['move_deadzone'] = round(app_data, 4)

    def on_pid_error_filter_alpha_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['pid_error_filter_alpha'] = round(float(app_data), 2)
        self._update_pid_params()

    def on_pid_vel_filter_alpha_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['pid_vel_filter_alpha'] = round(float(app_data), 2)
        self._update_pid_params()

    def on_tracker_enabled_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['tracker_enabled'] = bool(app_data)
        self.refresh_controller_params()

    def on_tracker_match_thresh_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['tracker_match_thresh'] = round(float(app_data), 2)
        self.refresh_controller_params()

    def on_tracker_track_buffer_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['tracker_track_buffer'] = int(app_data)
        self.refresh_controller_params()

    def on_min_lead_speed_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['min_lead_speed'] = round(float(app_data), 3)
        self.refresh_controller_params()

    def on_max_lead_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['max_lead'] = round(float(app_data), 3)
        self.refresh_controller_params()

    def on_lead_smooth_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['lead_smooth'] = round(float(app_data), 3)
        self.refresh_controller_params()

    def on_target_id_lock_change(self, sender, app_data):
        self.config['target_id_lock_enabled'] = bool(app_data)
        if hasattr(self, 'aim_pipeline') and self.aim_pipeline is not None:
            self.aim_pipeline.target_id_lock_enabled = bool(app_data)
        print(f'目标ID强锁定: {"启用" if app_data else "关闭"}')

    def on_kalman_enabled_change(self, sender, app_data):
        self.config.setdefault('kalman', {})['enabled'] = bool(app_data)
        if hasattr(self, 'aim_pipeline') and self.aim_pipeline is not None:
            self.aim_pipeline.kalman_enabled = bool(app_data)
        print(f'移动预测: {"启用" if app_data else "关闭"}')

    def on_kalman_predict_frames_change(self, sender, app_data):
        v = max(0, min(20, int(app_data)))
        self.config.setdefault('kalman', {})['predict_frames'] = v
        if hasattr(self, 'aim_pipeline') and self.aim_pipeline is not None:
            self.aim_pipeline.kalman_predict_frames = v
        print(f'预测系数: {v}')

    def on_kalman_predict_gain_change(self, sender, app_data):
        v = max(0.0, min(20.0, float(app_data)))
        self.config.setdefault('kalman', {})['predict_gain'] = v
        if hasattr(self, 'aim_pipeline') and self.aim_pipeline is not None:
            self.aim_pipeline.predict_gain = v
        print(f'预测增益: {v}')

    def on_target_switch_delay_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['target_switch_delay'] = app_data

    def on_target_reference_class_change(self, sender, app_data):
        try:
            class_id = int(app_data.replace('类别', ''))
        except (ValueError, AttributeError):
            class_id = 0
        self.config['groups'][self.group]['aim_keys'][self.select_key]['target_reference_class'] = class_id

    def _update_pid_params(self):
        """更新双轴PID控制器参数"""
        if hasattr(self, 'aim_pid'):
            self.refresh_controller_params()

    def _register_control_callback(self, control_id):
        """\n        为控件注册回调函数\n        \n        Args:\n            control_id: 控件ID\n        """
        dpg.set_item_callback(control_id, self.on_change)
