# -*- coding: utf-8 -*-
"""按键绑定 Mixin - 从 core.py 抽取的参数组/按键选择与绑定相关 UI 回调。

包括 render_group_combo / render_key_combo、on_key_change / update_key_inputs、
分组增删改 (on_add/delete_group/key)、类别多选 (create/remove_checkboxes、on_checkbox_change)、
按键绑定流程 (start/stop_key_binding、_mouse_binding_poll、capture_key_press、
on_key_binding_button_click/complete)、init_class_aim_positions_for_key。
所有方法通过 self.* 访问 Valorant 实例;通过 mix-in 继承可用。
"""
import time
import threading
import copy
import win32api
import win32con
import dearpygui.dearpygui as dpg
from util.function import key2str


class KeyBindMixin:
    """按键绑定与参数组/按键选择 Mixin。

    依赖 Valorant 提供:
      self.config / self.group / self.select_key / self.aim_key / self.aim_keys_dist
      self.key_binding_active / key_binding_callback / key_binding_button_tag /
      key_binding_status_tag / key_binding_tag / key_binding_start_time
      self.update_class_aim_combo() / self.update_target_reference_class_combo() /
      self.update_rect() (TriggerMixin) / self.get_current_class_num() / self.refresh_pressed_key_config()
    """

    def render_group_combo(self):
        if self.move_group_tag is not None:
            dpg.delete_item(self.move_group_tag)
        self.move_group_tag = dpg.add_combo(label='参数组', items=list(self.config['groups'].keys()), default_value=self.config['group'], callback=self.on_group_change, width=self.scaled_width_large, parent=self.dpg_group_tag)
        self.refresh_engine()

    def render_key_combo(self):
        if self.key_tag is not None:
            dpg.delete_item(self.key_tag)
        default_value = ''
        if len(self.aim_key) > 0:
            default_value = self.aim_key[0]
            if self.select_key in self.aim_key and self.select_key!= default_value:
                default_value = self.select_key
        self.select_key = default_value
        self.key_tag = dpg.add_combo(label='按键', items=self.aim_key, default_value=default_value, callback=self.on_key_change, width=self.scaled_width_large, parent=self.aim_key_combo_group)
        self.update_checkboxes_state(self.config['groups'][self.group]['aim_keys'][self.select_key]['classes'])

    def on_key_change(self, sender, app_data):
        self.select_key = app_data
        self.update_key_inputs()
        self.update_checkboxes_state(self.config['groups'][self.group]['aim_keys'][self.select_key]['classes'])
        print(f'changed to: {self.select_key}')

    def update_key_inputs(self):
        if len(self.aim_key) > 0:
            self.update_class_aim_combo()
            self.update_target_reference_class_combo()
            self.update_class_aim_inputs()
            if self.class_priority_input is not None:
                priority_order = self.get_class_priority_order()
                priority_text = self.format_class_priority(priority_order)
                dpg.set_value(self.class_priority_input, priority_text)
            dpg.set_value(self.aim_bot_scope_slider, self.config['groups'][self.group]['aim_keys'][self.select_key]['aim_bot_scope'])
            dpg.set_value(self.min_position_offset_slider, self.config['groups'][self.group]['aim_keys'][self.select_key]['min_position_offset'])
            dpg.set_value(self.status_input, self.config['groups'][self.group]['aim_keys'][self.select_key]['trigger']['status'])
            dpg.set_value(self.continuous_trigger_input, self.config['groups'][self.group]['aim_keys'][self.select_key]['trigger'].get('continuous', False))
            dpg.set_value(self.trigger_recoil_input, self.config['groups'][self.group]['aim_keys'][self.select_key]['trigger'].get('recoil', False))
            dpg.set_value(self.start_delay_slider, self.config['groups'][self.group]['aim_keys'][self.select_key]['trigger']['start_delay'])
            dpg.set_value(self.press_delay_slider, self.config['groups'][self.group]['aim_keys'][self.select_key]['trigger']['press_delay'])
            dpg.set_value(self.end_delay_slider, self.config['groups'][self.group]['aim_keys'][self.select_key]['trigger']['end_delay'])
            dpg.set_value(self.random_delay_slider, self.config['groups'][self.group]['aim_keys'][self.select_key]['trigger']['random_delay'])
            dpg.set_value(self.x_trigger_scope_slider, self.config['groups'][self.group]['aim_keys'][self.select_key]['trigger']['x_trigger_scope'])
            dpg.set_value(self.y_trigger_scope_slider, self.config['groups'][self.group]['aim_keys'][self.select_key]['trigger']['y_trigger_scope'])
            dpg.set_value(self.x_trigger_offset_slider, self.config['groups'][self.group]['aim_keys'][self.select_key]['trigger']['x_trigger_offset'])
            dpg.set_value(self.y_trigger_offset_slider, self.config['groups'][self.group]['aim_keys'][self.select_key]['trigger']['y_trigger_offset'])
            self.update_rect()
            if self.auto_y_checkbox is not None:
                dpg.set_value(self.auto_y_checkbox, self.config['groups'][self.group]['aim_keys'][self.select_key].get('auto_y', False))
            if self.use_crosshair_checkbox is not None:
                dpg.set_value(self.use_crosshair_checkbox, self.config['groups'][self.group]['aim_keys'][self.select_key].get('use_crosshair', True))
                dpg.show_item(self.pid_params_group)
            key_cfg = self.config['groups'][self.group]['aim_keys'][self.select_key]
            dpg.set_value(self.pid_kp_x_slider, key_cfg.get('pid_kp_x', 0.4))
            dpg.set_value(self.pid_kp_y_slider, key_cfg.get('pid_kp_y', 0.4))
            dpg.set_value(self.pid_ki_x_slider, key_cfg.get('pid_ki_x', 0.02))
            dpg.set_value(self.pid_ki_y_slider, key_cfg.get('pid_ki_y', 0.02))
            dpg.set_value(self.pid_kd_x_slider, key_cfg.get('pid_kd_x', 0.12))
            dpg.set_value(self.pid_kd_y_slider, key_cfg.get('pid_kd_y', 0.12))
            dpg.set_value(self.pid_integral_limit_x_slider, key_cfg.get('pid_integral_limit_x', 0.0))
            dpg.set_value(self.pid_integral_limit_y_slider, key_cfg.get('pid_integral_limit_y', 0.0))
            dpg.set_value(self.smooth_x_slider, key_cfg.get('smooth_x', 0.0))
            dpg.set_value(self.smooth_y_slider, key_cfg.get('smooth_y', 0))
            dpg.set_value(self.smooth_deadzone_slider, key_cfg.get('smooth_deadzone', 0.0))
            dpg.set_value(self.smooth_algorithm_slider, key_cfg.get('smooth_algorithm', 1.0))
            dpg.set_value(self.move_deadzone_slider, key_cfg.get('move_deadzone', 1.0))
            if self.pid_error_filter_alpha_slider is not None:
                dpg.set_value(self.pid_error_filter_alpha_slider, float(key_cfg.get('pid_error_filter_alpha', 0.0)))
            if self.pid_vel_filter_alpha_slider is not None:
                dpg.set_value(self.pid_vel_filter_alpha_slider, float(key_cfg.get('pid_vel_filter_alpha', 0.0)))
            if self.tracker_enabled_checkbox is not None:
                dpg.set_value(self.tracker_enabled_checkbox, bool(key_cfg.get('tracker_enabled', True)))
            if self.tracker_match_thresh_slider is not None:
                dpg.set_value(self.tracker_match_thresh_slider, float(key_cfg.get('tracker_match_thresh', 0.3)))
            if self.tracker_track_buffer_slider is not None:
                dpg.set_value(self.tracker_track_buffer_slider, int(key_cfg.get('tracker_track_buffer', 30)))
            if self.target_id_lock_checkbox is not None:
                dpg.set_value(self.target_id_lock_checkbox, bool(self.config.get('target_id_lock_enabled', True)))
            if self.kalman_enabled_checkbox is not None:
                dpg.set_value(self.kalman_enabled_checkbox, bool(self.config.get('kalman', {}).get('enabled', True)))
            if self.kalman_predict_frames_slider is not None:
                dpg.set_value(self.kalman_predict_frames_slider, int(self.config.get('kalman', {}).get('predict_frames', 5)))
            dpg.set_value(self.target_switch_delay_slider, key_cfg.get('target_switch_delay', 0))
            reference_class = key_cfg.get('target_reference_class', 0)
            dpg.set_value(self.target_reference_class_combo, f'类别{reference_class}')
            dyn = key_cfg.get('dynamic_scope', {}) or {}
            if self.dynamic_scope_enabled_input is not None:
                dpg.set_value(self.dynamic_scope_enabled_input, bool(dyn.get('enabled', False)))
            if self.dynamic_scope_min_scope_slider is not None:
                if 'min_scope' in dyn:
                    dpg.set_value(self.dynamic_scope_min_scope_slider, int(dyn.get('min_scope', 0)))
                else:
                    base_scope = int(key_cfg.get('aim_bot_scope', 0))
                    ratio = float(dyn.get('min_ratio', 0.5))
                    dpg.set_value(self.dynamic_scope_min_scope_slider, int(base_scope * max(0.0, min(1.0, ratio))))
            if self.dynamic_scope_shrink_ms_slider is not None:
                dpg.set_value(self.dynamic_scope_shrink_ms_slider, int(dyn.get('shrink_duration_ms', 300)))
            if self.dynamic_scope_recover_ms_slider is not None:
                dpg.set_value(self.dynamic_scope_recover_ms_slider, int(dyn.get('recover_duration_ms', 300)))

    def update_group_inputs(self):
        dpg.set_value(self.infer_model_input, self.config['groups'][self.group]['infer_model'])
        dpg.set_value(self.is_trt_checkbox, self.config['groups'][self.group]['is_trt'])
        dpg.set_value(self.is_v8_checkbox, self.config['groups'][self.group]['is_v8'])
        dpg.set_value(self.right_down_checkbox, self.config['groups'][self.group]['right_down'])
        self.update_key_inputs()

    def create_checkboxes(self, options):
        self.remove_checkboxes()
        for option in options:
            checkbox_tag = dpg.add_checkbox(label=str(option), callback=self.on_checkbox_change, parent=self.checkbox_group_tag)
            self.checkboxes.append(checkbox_tag)
            if option in self.selected_items:
                dpg.set_value(checkbox_tag, True)

    def remove_checkboxes(self):
        for checkbox in self.checkboxes:
            dpg.delete_item(checkbox)
        self.checkboxes.clear()

    def on_checkbox_change(self, sender, app_data):
        if app_data:
            self.selected_items.append(int(dpg.get_item_label(sender)))
        else:
            self.selected_items.remove(int(dpg.get_item_label(sender)))
        self.config['groups'][self.group]['aim_keys'][self.select_key]['classes'] = self.selected_items
        print(f'当前选择项: {self.selected_items}')
        if hasattr(self, 'old_pressed_aim_key') and self.old_pressed_aim_key:
            self.refresh_pressed_key_config(self.old_pressed_aim_key)
            print(f'已刷新按键 {self.old_pressed_aim_key} 的类别配置，推理将实时生效')

    def update_checkboxes_state(self, new_selection):
        for checkbox in self.checkboxes:
            option = int(dpg.get_item_label(checkbox))
            should_be_selected = option in new_selection
            dpg.set_value(checkbox, should_be_selected)
        self.selected_items = new_selection

    def on_delete_group_click(self, sender, app_data):
        if len(self.config['groups']) > 1:
            del self.config['groups'][self.group]
            self.group = list(self.config['groups'].keys())[0]
            self.config['group'] = self.group
            self.render_group_combo()
            self.refresh_engine()
            class_num = self.get_current_class_num()
            class_ary = list(range(class_num))
            self.create_checkboxes(class_ary)
            self.update_class_aim_combo()
            self.update_target_reference_class_combo()
            self.aim_keys_dist = self.config['groups'][self.group]['aim_keys']
            self.aim_key = list(self.aim_keys_dist.keys())
            self.render_key_combo()
            self.update_group_inputs()

    def on_group_name_change(self, sender, app_data):
        self.add_group_name = app_data

    def on_add_group_click(self, sender, app_data):
        if self.add_group_name not in self.config['groups'] and self.add_group_name!= '':
            self.config['groups'][self.add_group_name] = copy.deepcopy(self.config['groups'][self.group])
            self.group = self.add_group_name
            self.config['group'] = self.group
            self.render_group_combo()

    def on_delete_key_click(self, sender, app_data):
        if len(self.config['groups'][self.group]['aim_keys']) > 1:
            del self.config['groups'][self.group]['aim_keys'][self.select_key]
            self.aim_keys_dist = self.config['groups'][self.group]['aim_keys']
            self.aim_key = list(self.aim_keys_dist.keys())
            self.select_key = self.aim_key[0]
            self.render_key_combo()
            self.update_key_inputs()

    def on_key_name_change(self, sender, app_data):
        self.add_key_name = app_data

    def on_add_key_click(self, sender, app_data):
        if self.add_key_name not in self.config['groups'][self.group]['aim_keys'] and self.add_key_name!= '':
            self.config['groups'][self.group]['aim_keys'][self.add_key_name] = copy.deepcopy(self.config['groups'][self.group]['aim_keys'][self.select_key])
            self.init_class_aim_positions_for_key(self.add_key_name)
            self.aim_keys_dist = self.config['groups'][self.group]['aim_keys']
            self.aim_key = list(self.aim_keys_dist.keys())
            self.select_key = self.add_key_name
            self.render_key_combo()
            self.update_class_aim_combo()
            self.update_target_reference_class_combo()

    def start_key_binding(self, sender, app_data, callback=None):
        """开始按键绑定模式

        在GUI内部点击按钮会被窗口消费，使 pynput 无法收到该次鼠标事件。
        为了确保任何鼠标按键都能被检测到，我们另外开启一个后台
        轮询线程，使用 ``GetAsyncKeyState`` 直接查询键盘状态。
        """
        if self.key_binding_active:
            # 如果已经在绑定模式，则停止
            self.stop_key_binding()
            return

        self.key_binding_active = True
        self.key_binding_callback = callback
        # 记录开始时间，用于忽略由绑定按钮自身产生的鼠标事件
        self.key_binding_start_time = time.time()

        # 启动轮询线程检测鼠标按键
        threading.Thread(target=self._mouse_binding_poll, daemon=True).start()

        # 更新按钮状态
        if self.key_binding_button_tag:
            dpg.configure_item(self.key_binding_button_tag, label="取消绑定")

        # 更新状态显示 - 使用橙色表示等待状态
        if self.key_binding_status_tag:
            dpg.set_value(self.key_binding_status_tag, "等待按键...")
            dpg.configure_item(self.key_binding_status_tag, color=[255, 165, 0])  # 橙色

        print("按键绑定模式已启动，请按下要绑定的按键...")

    def stop_key_binding(self):
        """停止按键绑定模式"""
        if not self.key_binding_active:
            return
        
        self.key_binding_active = False
        self.key_binding_callback = None
        
        # 更新按钮状态
        if self.key_binding_button_tag:
            dpg.configure_item(self.key_binding_button_tag, label="按下键绑定")
        
        # 更新状态显示 - 使用黄色表示等待绑定状态
        if self.key_binding_status_tag:
            dpg.set_value(self.key_binding_status_tag, "等待绑定")
            dpg.configure_item(self.key_binding_status_tag, color=[255, 255, 0])  # 黄色
        
        print("按键绑定模式已取消")

    def _mouse_binding_poll(self):
        """后台轮询物理鼠标按键状态并执行绑定。

        即使GUI窗口拥有焦点，`GetAsyncKeyState` 也能检测到按键。
        轮询到第一个按下按钮后立即调用 `capture_key_press` 并退出。
        """
        mapping = {
            win32con.VK_LBUTTON: 'mouse_left',
            win32con.VK_RBUTTON: 'mouse_right',
            win32con.VK_MBUTTON: 'mouse_middle',
            win32con.VK_XBUTTON1: 'mouse_x1',
            win32con.VK_XBUTTON2: 'mouse_x2',
        }
        # 持续检查直到绑定模式被取消或找到按键
        while self.key_binding_active:
            for vk, name in mapping.items():
                if win32api.GetAsyncKeyState(vk) & 0x8000:
                    self.capture_key_press(name)
                    return
            time.sleep(0.01)

    def capture_key_press(self, key):
        """捕获按键按下事件"""
        if not self.key_binding_active:
            return
        
        # 将按键转换为字符串
        key_str = key2str(key)
        
        # 过滤掉一些特殊按键
        if key_str in ['esc', 'escape']:
            self.stop_key_binding()
            return
        
        # 更新状态显示 - 使用绿色表示绑定成功
        if self.key_binding_status_tag:
            dpg.set_value(self.key_binding_status_tag, f"已绑定: {key_str}")
            dpg.configure_item(self.key_binding_status_tag, color=[0, 255, 0])  # 绿色
        
        # 更新输入框
        if self.key_binding_tag:
            dpg.set_value(self.key_binding_tag, key_str)
        
        # 执行回调函数
        if self.key_binding_callback:
            self.key_binding_callback(key_str)
        
        # 停止绑定模式
        self.stop_key_binding()
        
        print(f"按键绑定成功: {key_str}")
        
        # 执行回调函数
        if self.key_binding_callback:
            self.key_binding_callback(key_str)
        
        # 停止绑定模式
        self.stop_key_binding()
        
        print(f"按键绑定成功: {key_str}")

    def on_key_binding_button_click(self, sender, app_data):
        """按键绑定按钮点击事件"""
        self.start_key_binding(sender, app_data, callback=self.on_key_binding_complete)

    def on_key_binding_complete(self, key_name):
        """按键绑定完成回调 - 直接执行添加操作"""
        # 直接添加键（如果键名有效且不存在）
        if key_name and key_name not in self.config['groups'][self.group]['aim_keys']:
            # 复制当前选中键的配置
            self.config['groups'][self.group]['aim_keys'][key_name] = copy.deepcopy(self.config['groups'][self.group]['aim_keys'][self.select_key])
            # 初始化新键的类别瞄准位置配置
            self.init_class_aim_positions_for_key(key_name)
            # 更新相关变量
            self.aim_keys_dist = self.config['groups'][self.group]['aim_keys']
            self.aim_key = list(self.aim_keys_dist.keys())
            self.select_key = key_name
            # 刷新界面
            self.render_key_combo()
            self.update_class_aim_combo()
            self.update_target_reference_class_combo()
            
            print(f"按键已成功添加: {key_name}")
        elif key_name in self.config['groups'][self.group]['aim_keys']:
            print(f"按键已存在: {key_name}")
        else:
            print("无效的按键名称")

    def init_class_aim_positions_for_key(self, key_name):
        """为指定按键初始化类别瞄准位置配置"""
        try:
            class_num = self.get_current_class_num()
            key_config = self.config['groups'][self.group]['aim_keys'][key_name]
            if 'class_aim_positions' not in key_config:
                key_config['class_aim_positions'] = {}
            if 'class_priority_order' not in key_config:
                key_config['class_priority_order'] = list(range(class_num))
            for i in range(class_num):
                class_str = str(i)
                if class_str not in key_config['class_aim_positions']:
                    key_config['class_aim_positions'][class_str] = {'aim_bot_position': 0.0, 'aim_bot_position2': 0.0, 'confidence_threshold': 0.5, 'iou_t': 1.0}
        except Exception as e:
            print(f'初始化类别瞄准位置配置失败: {e}')
