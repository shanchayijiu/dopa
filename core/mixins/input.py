# -*- coding: utf-8 -*-
"""输入监听 Mixin — 从 core.py 提取的 pynput 键鼠事件处理层。

包含鼠标按钮到内部键名的映射、鼠标点击/滚轮回调、键盘按下/抬起回调、
目标锁定状态复位与 PID 复位。这些回调由 core_devices.py 注册进
pynput 的 keyboard.Listener / mouse.Listener，在监听线程中被调用。

组内自洽：on_click 经 _mouse_button_to_key 解析按钮，三个事件回调调用
reset_pid，on_release 额外调用 reset_target_lock。

依赖 Valorant 提供:
  self.config / self.aim_key / self.pressed_key / self.aim_pid
  self.key_binding_active / self.capture_key_press()（KeyBindMixin）
  self.left_press() / self.left_release()（DeviceMixin）
  self.refresh_pressed_key_config()（ConfigMixin）
  self.reset_dynamic_aim_scope() / self.handle_color_pick_hotkey()（CrosshairUIMixin）
  self.stop_continuous_trigger() / self.stop_trigger_recoil()（TriggerMixin）
  self.update_mouse_re_ui_status() / self._stop_mouse_re_recoil()（MouseReMixin）
  self.time_set_event() / self.time_kill_event() / self.down
"""
import time

from pynput import mouse
from util.function import key2str


class InputListenerMixin:
    """pynput 键鼠事件处理 Mixin。"""

    def _mouse_button_to_key(self, button):
        """Convert a pynput mouse.Button to our internal key string.

        最少代码重构：直接使用字典查找，方便扩展并减少冗余分支。
        如果按钮不在映射中返回 ``None``。
        """
        mapping = {
            mouse.Button.left:   'mouse_left',
            mouse.Button.right:  'mouse_right',
            mouse.Button.middle: 'mouse_middle',
            mouse.Button.x1:     'mouse_x1',
            mouse.Button.x2:     'mouse_x2',
        }
        return mapping.get(button)

    def on_click(self, x, y, button, pressed):
        key = self._mouse_button_to_key(button)
        if key is None:
            return

        # 绑定模式期间优先处理：
        if self.key_binding_active:
            # 依旧保留时间忽略机制，防止按钮自身事件触发
            if time.time() - self.key_binding_start_time < 0.2:
                return
            self.capture_key_press(key)
            return

        if pressed:
            if key == 'mouse_left':
                if not self.left_pressed:
                    self.left_press()
            elif key == 'mouse_right':
                if not self.right_pressed:
                    self.right_pressed = True

            if key in self.aim_key and self.old_pressed_aim_key == '':
                self.refresh_pressed_key_config(key)
                self.old_pressed_aim_key = key
                self.aim_key_status = True
                self.reset_dynamic_aim_scope(key)
        elif key == 'mouse_left':
            if self.left_pressed:
                self.left_release()
        elif key == 'mouse_right':
            if self.right_pressed:
                self.right_pressed = False

        if key in self.aim_key and key == self.old_pressed_aim_key:
            self.old_pressed_aim_key = ''
            self.aim_key_status = False
            self.reset_pid()

    def on_scroll(self, x, y, dx, dy):
        pass

    def on_press(self, key):
        # 首先检查是否在按键绑定模式
        if self.key_binding_active:
            self.capture_key_press(key)
            return
        
        key = key2str(key)
        if key == 'f3':
            self.handle_color_pick_hotkey()
            return
        if key in self.aim_key and key not in self.pressed_key and (self.old_pressed_aim_key == ''):
            self.refresh_pressed_key_config(key)
            self.reset_pid()
            self.old_pressed_aim_key = key
            self.aim_key_status = True
         
        if key not in self.pressed_key:
            self.pressed_key.append(key)

    def on_release(self, key):
        key = key2str(key)
        if key == self.config['down_switch_key']:
     
            self.down_switch = not self.down_switch
            if self.down_switch:
                if not self.config.get('recoil', {}).get('use_mouse_re_trajectory', False):
                    self.timer_id2 = self.time_set_event(self.delay, 1, self.down, 0, 1)
            else:
                if self.timer_id2!= 0:
                    self.time_kill_event(self.timer_id2)
                    self.timer_id2 = 0
                if getattr(self, '_recoil_is_replaying', False):
               
                    self._stop_mouse_re_recoil()
            print('压枪开' if self.down_switch else '压枪关')
            self.update_mouse_re_ui_status()
        if key in self.aim_key and key == self.old_pressed_aim_key:
            self.old_pressed_aim_key = ''
            self.aim_key_status = False
            self.reset_pid()
            self.reset_target_lock(key)
        if key in self.pressed_key:
            self.pressed_key.remove(key)

    def reset_target_lock(self, key=None):
        # 
        #         重置目标锁定相关状态，确保松开自瞄键后下次按下能重新选择目标。
        #         该方法仅清理状态，不做任何阻塞操作；所有字段均做存在性检查以保证兼容。
        #         
        try:
            if hasattr(self, 'is_waiting_for_switch'):
                self.is_waiting_for_switch = False
            if hasattr(self, 'target_switch_time'):
                self.target_switch_time = 0
            possible_attrs_to_none = ['current_target', 'locked_target', 'selected_target', 'target', 'target_bbox', 'target_box', 'last_target', 'best_target', 'last_best_target', 'current_target_id', 'last_target_id']
            for attr_name in possible_attrs_to_none:
                if hasattr(self, attr_name):
                    try:
                        setattr(self, attr_name, None)
                    except Exception:
                        pass
            if hasattr(self, 'target_history') and isinstance(self.target_history, dict):
                try:
                    self.target_history.clear()
                except Exception:
                    pass
            if hasattr(self, '_clear_queues') and callable(self._clear_queues):
                try:
                    self._clear_queues()
                except Exception:
                    pass
            for flag_name in ('trigger_status', 'continuous_trigger_active', 'trigger_recoil_active'):
             
                if hasattr(self, flag_name):
                    try:
                        setattr(self, flag_name, False)
                    except Exception:
                        pass
        except Exception:
            return

    def reset_pid(self):
        self.aim_pid.reset()
        self.last_target_count = 0
        self.last_target_count_by_class.clear()
        self.is_waiting_for_switch = False
        self.target_switch_time = 0
        self.stop_continuous_trigger()
        self.stop_trigger_recoil()
