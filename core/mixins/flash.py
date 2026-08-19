# -*- coding: utf-8 -*-
"""自动背闪 Mixin - 从 core.py 抽取的背闪/flashbang 相关 UI 回调。

包括背闪启用/延迟/角度/灵敏度/回转/曲线/置信度/尺寸/调试等配置回调,
以及测试左右转背闪、调试信息、UI 状态同步。
所有方法通过 self.* 访问 Valorant 实例;通过 mix-in 继承可用。
"""

from devices.flashbang_handler import FlashbangHandler


class FlashbangMixin:
    """自动背闪相关回调 Mixin。

    依赖 Valorant 提供:
      self.config['auto_flashbang'] / self.group / self.decrypted_model_data / self._flashbang / self.move_r
      self.is_using_dopa_model() / self._get_flashbang()
    """

    def on_auto_flashbang_enabled_change(self, sender, app_data):
        if not self.is_using_dopa_model():
            print('自动背闪功能仅支持ZTX模型，当前模型不支持')
            self.config['auto_flashbang']['enabled'] = False
            try:
                import dearpygui.dearpygui as dpg
                if dpg.does_item_exist('auto_flashbang_enabled_checkbox'):
                    dpg.set_value('auto_flashbang_enabled_checkbox', False)
            except Exception:
                return None
        else:
            self.config['auto_flashbang']['enabled'] = app_data
            print(f"自动背闪已{('启用' if app_data else '禁用')}")

    def on_auto_flashbang_delay_change(self, sender, app_data):
        if not self.is_using_dopa_model():
            print('自动背闪功能仅支持ZTX模型，当前模型不支持')
            return
        self.config['auto_flashbang']['delay_ms'] = app_data
        print(f'背闪延迟设置为: {app_data}ms')

    def on_auto_flashbang_angle_change(self, sender, app_data):
        if not self.is_using_dopa_model():
            print('自动背闪功能仅支持ZTX模型，当前模型不支持')
            return
        self.config['auto_flashbang']['turn_angle'] = app_data
        print(f'背闪转向角度设置为: {app_data}度')

    def on_auto_flashbang_sensitivity_change(self, sender, app_data):
        if not self.is_using_dopa_model():
            print('自动背闪功能仅支持ZTX模型，当前模型不支持')
            return
        self.config['auto_flashbang']['sensitivity_multiplier'] = app_data
        print(f'背闪灵敏度倍数设置为: {app_data}')

    def on_auto_flashbang_return_delay_change(self, sender, app_data):
        if not self.is_using_dopa_model():
            print('自动背闪功能仅支持ZTX模型，当前模型不支持')
            return
        self.config['auto_flashbang']['return_delay'] = app_data
        print(f'背闪回转延迟设置为: {app_data}ms')

    def on_test_flashbang_left(self, sender, app_data):
        """测试左转背闪"""
        if not self.is_using_dopa_model():
            print('自动背闪功能仅支持ZTX模型，当前模型不支持')
            return
        print('测试左转背闪...')
        self._get_flashbang()._turn((-1), self.config['auto_flashbang'])

    def on_test_flashbang_right(self, sender, app_data):
        """测试右转背闪"""
        if not self.is_using_dopa_model():
            print('自动背闪功能仅支持ZTX模型，当前模型不支持')
            return
        print('测试右转背闪...')
        self._get_flashbang()._turn(1, self.config['auto_flashbang'])

    def on_auto_flashbang_curve_change(self, sender, app_data):
        if not self.is_using_dopa_model():
            print('自动背闪功能仅支持ZTX模型，当前模型不支持')
            return
        self.config['auto_flashbang']['use_curve'] = app_data
        print(f"背闪曲线移动已{('启用' if app_data else '禁用')}")

    def on_auto_flashbang_curve_speed_change(self, sender, app_data):
        if not self.is_using_dopa_model():
            print('自动背闪功能仅支持ZTX模型，当前模型不支持')
            return
        self.config['auto_flashbang']['curve_speed'] = app_data
        print(f'背闪曲线速度设置为: {app_data}')

    def on_auto_flashbang_curve_knots_change(self, sender, app_data):
        if not self.is_using_dopa_model():
            print('自动背闪功能仅支持ZTX模型，当前模型不支持')
            return
        self.config['auto_flashbang']['curve_knots'] = app_data
        print(f'背闪曲线控制点数量设置为: {app_data}个')

    def on_auto_flashbang_min_confidence_change(self, sender, app_data):
        if not self.is_using_dopa_model():
            print('自动背闪功能仅支持ZTX模型，当前模型不支持')
            return
        self.config['auto_flashbang']['min_confidence'] = app_data
        print(f'背闪最小置信度设置为: {app_data}')

    def on_auto_flashbang_min_size_change(self, sender, app_data):
        if not self.is_using_dopa_model():
            print('自动背闪功能仅支持ZTX模型，当前模型不支持')
            return
        self.config['auto_flashbang']['min_size'] = app_data
        print(f'背闪最小尺寸设置为: {app_data}像素')

    def on_flashbang_debug_info(self, sender, app_data):
        """显示自动背闪调试信息"""
        import time
        print('=== 自动背闪调试信息 ===')
        print(f"功能状态: {('启用' if self.config['auto_flashbang']['enabled'] else '禁用')}")
        dopa_status = self.is_using_dopa_model()
        print(f"ZTX模型状态: {('已加载' if dopa_status else '未使用/未加载')}")
        if hasattr(self, 'group') and self.group:
            current_model = self.config['groups'][self.group].get('infer_model', '')
        print(f"功能可用性: {('可用' if self.config['auto_flashbang']['enabled'] and dopa_status else '不可用')}")
        print('配置参数:')
        for key, value in self.config['auto_flashbang'].items():
            print(f'  {key}: {value}')
        fb = self._get_flashbang()
        print(f'上次触发时间: {time.time() - fb.last_time:.1f}秒前')
        print(f'冷却时间: {fb.cooldown}秒')
        print(f'是否正在回转: {fb.is_turning_back}')
        if hasattr(self, 'group') and self.group:
            current_model = self.config['groups'][self.group].get('infer_model', '')
            print(f'当前模型: {current_model}')
            print(f"解密数据状态: {('已加载' if self.decrypted_model_data is not None else '未加载')}")
        print('=====================')

    def update_auto_flashbang_ui_state(self):
        """更新自动背闪UI控件的启用/禁用状态"""
        try:
            import dearpygui.dearpygui as dpg
            is_dopa = self.is_using_dopa_model()
            auto_flashbang_controls = ['auto_flashbang_enabled_checkbox', 'auto_flashbang_delay_input', 'auto_flashbang_angle_input', 'auto_flashbang_sensitivity_input', 'auto_flashbang_return_delay_input', 'auto_flashbang_curve_checkbox', 'auto_flashbang_curve_speed_input', 'auto_flashbang_curve_knots_input', 'auto_flashbang_min_confidence_input', 'auto_flashbang_min_size_input', 'auto_flashbang_test_left_button', 'auto_flashbang_test_right_button', 'auto_flashbang_debug_button']
            for control_tag in auto_flashbang_controls:
                if dpg.does_item_exist(control_tag):
                    dpg.configure_item(control_tag, enabled=is_dopa)
            if not is_dopa:
                if self.config['auto_flashbang']['enabled']:
                    self.config['auto_flashbang']['enabled'] = False
                    if dpg.does_item_exist('auto_flashbang_enabled_checkbox'):
                        dpg.set_value('auto_flashbang_enabled_checkbox', False)
        except Exception as e:
            print(f'更新自动背闪UI状态时出错: {e}')

    # --- 以下为从 core.py 迁入的 FlashbangHandler 委托层 ---
    # 原先留在 core.py,而本 mixin 的回调已在调用 self._get_flashbang(),
    # 迁入后背闪子域自洽,不再反向依赖 core.py。

    def _get_flashbang(self):
        if self._flashbang is None:
            self._flashbang = FlashbangHandler(self.move_r)
        return self._flashbang

    def detect_and_handle_flashbang(self, boxes, class_ids, model_width, model_height, scores=None):
        self._get_flashbang().detect_and_handle(boxes, class_ids, model_width, model_height, self.config['auto_flashbang'], scores)

    def execute_flashbang_turn(self, turn_direction):
        self._get_flashbang()._turn(turn_direction, self.config['auto_flashbang'])

    def execute_flashbang_return(self, original_turn_direction):
        self._get_flashbang()._return(original_turn_direction, self.config['auto_flashbang'])

    def execute_flashbang_curve_move(self, relative_move_x, relative_move_y):
        self._get_flashbang().curve_move(relative_move_x, relative_move_y, self.config['auto_flashbang'], self.config)

    def execute_flashbang_curve_move_fast(self, relative_move_x, relative_move_y):
        self._get_flashbang().curve_move(relative_move_x, relative_move_y, self.config['auto_flashbang'], self.config)

    def execute_flashbang_curve_move_with_tracking(self, relative_move_x, relative_move_y):
        return self._get_flashbang().curve_move_with_tracking(relative_move_x, relative_move_y, self.config['auto_flashbang'], self.config)

    def execute_flashbang_ultra_fast_move(self, relative_move_x, relative_move_y):
        return self._get_flashbang()._ultra_fast_move(relative_move_x, relative_move_y, self.config['auto_flashbang'])
