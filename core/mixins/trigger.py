# -*- coding: utf-8 -*-
"""触发器 Mixin — 从 core.py 提取的触发器逻辑。

包含自动扣枪触发(trigger)、连续触发(continuous_trigger_process)、
触发器后坐力补偿(start/stop_trigger_recoil)、鼠标按下/释放(mouse_left_down/up)。
所有方法操作 self.* 属性，由 Valorant.__init__ 创建，通过 mix-in 继承可用。
"""
import time
import random
import threading
from threading import Thread
import ctypes
import kmNet
import pydirectinput
import queue
from devices.catbox_wrapper import catbox_left_down, catbox_left_up
import dearpygui.dearpygui as dpg


class TriggerMixin:
    """触发器 Mixin。

    方法依赖 Valorant.__init__ 中建立的属性：
      self.move_r / self.left_pressed / self.press_timer /
      self.trigger_status / self.continuous_trigger_active /
      self.aim_key_status / self.pressed_key_config 等。
    """

    def mouse_left_down(self):
        if self.config['move_method'] == 'dhz':
            self.dhz.left(1)
        elif self.config['move_method'] == 'pnmh':
            self.pnmh.LeftDown()
        if self.config['move_method'] == 'km_net':
            kmNet.left(1)
        elif self.config['move_method'] == 'km_box_a':
            self.move_dll.KM_left(ctypes.c_char(1))
        elif self.config['move_method'] == 'send_input':
            pydirectinput.mouseDown(button='left')
        elif self.config['move_method'] == 'logitech':
            self.move_dll.mouse_down(1)
        elif self.config['move_method'] == 'makcu':
            if self.makcu is not None:
                max_retries = 3
                for retry in range(max_retries):
                    try:
                        self.makcu.left(1)
                        return
                    except Exception as e:
                        if retry == max_retries - 1:
                            print(f'Makcu点击失败: {e}')
                            try:
                                self.makcu.disconnect()
                                time.sleep(0.1)
                                self.makcu.connect()
                            except Exception as e:
                                print(f'Makcu点击后重连失败: {e}')
                        else:
                            time.sleep(0.1)
        elif self.config['move_method'] == 'catbox':
            catbox_left_down()

    def mouse_left_up(self):
        if self.config['move_method'] == 'dhz':
            self.dhz.left(0)
        elif self.config['move_method'] == 'pnmh':
            self.pnmh.LeftUp()
        if self.config['move_method'] == 'km_net':
            kmNet.left(0)
        elif self.config['move_method'] == 'km_box_a':
            self.move_dll.KM_left(ctypes.c_char(0))
        elif self.config['move_method'] == 'send_input':
            pydirectinput.mouseUp(button='left')
        elif self.config['move_method'] == 'logitech':
            self.move_dll.mouse_up(1)
        elif self.config['move_method'] == 'makcu':
            if self.makcu is not None:
                max_retries = 3
                for retry in range(max_retries):
                    try:
                        self.makcu.left(0)
                        return
                    except Exception as e:
                        if retry == max_retries - 1:
                            print(f'Makcu释放失败: {e}')
                            try:
                                self.makcu.disconnect()
                                time.sleep(0.1)
                                self.makcu.connect()
                            except Exception as e:
                                print(f'Makcu释放后重连失败: {e}')
                        else:
                            time.sleep(0.1)
        elif self.config['move_method'] == 'catbox':
            catbox_left_up()

    def trigger_process(self, start_delay=0, press_delay=1, end_delay=0, random_delay=0, recoil_enabled=False):
        self.time_begin_period(1)
        if start_delay > 0:
            if random_delay > 0:
                start_delay = random.randint(max(0, start_delay - random_delay), start_delay + random_delay)
            time.sleep(start_delay / 1000)
        self.mouse_left_down()
        if recoil_enabled:
            self.start_trigger_recoil()
        if press_delay > 0:
            if random_delay > 0:
                press_delay = random.randint(max(0, press_delay - random_delay), press_delay + random_delay)
            time.sleep(press_delay / 1000)
        self.mouse_left_up()
        if recoil_enabled:
            self.stop_trigger_recoil()
        if end_delay > 0:
            if random_delay > 0:
                end_delay = random.randint(max(0, end_delay - random_delay), end_delay + random_delay)
            time.sleep(end_delay / 1000)
        self.trigger_status = False

    def continuous_trigger_process(self, recoil_enabled=False):
        """持续扳机处理函数 - 一直开枪直到按键松开"""
        self.time_begin_period(1)
        start_delay = self.pressed_key_config['trigger']['start_delay']
        random_delay = self.pressed_key_config['trigger']['random_delay']
        if start_delay > 0:
            if random_delay > 0:
                actual_start_delay = random.randint(max(0, start_delay - random_delay), start_delay + random_delay)
            else:
                actual_start_delay = start_delay
            time.sleep(actual_start_delay / 1000)
        self.mouse_left_down()
        if recoil_enabled:
            self.start_trigger_recoil()
        try:
            while self.aim_key_status and self.continuous_trigger_active:
                time.sleep(0.01)
        finally:
            self.mouse_left_up()
            if recoil_enabled:
                self.stop_trigger_recoil()
            self.continuous_trigger_active = False

    def stop_continuous_trigger(self):
        """停止持续扳机"""
        if self.continuous_trigger_active:
            self.continuous_trigger_active = False

    def start_trigger_recoil(self):
        """启动扳机压枪"""
        if self.trigger_recoil_active:
            return
        if self.config.get('recoil', {}).get('use_mouse_re_trajectory', False):
            try:
                self._load_mouse_re_trajectory_for_current()
                if self._current_mouse_re_points:
                    self.trigger_recoil_active = True
                    self._recoil_is_replaying = True
                    self.trigger_recoil_thread = threading.Thread(target=self._recoil_replay_worker, args=(self._current_mouse_re_points,), daemon=True)
                    self.trigger_recoil_thread.start()
                    print('扳机压枪已启动 (mouse_re模式)')
            except Exception as e:
                print(f'扳机压枪启动失败: {e}')
        if not self.trigger_recoil_active:
            self.trigger_recoil_active = True
            self.trigger_recoil_pressed = True
            self.end = False
            self.now_num = 0
            self.now_stage = 0
            self.timer_id2 = self.time_set_event(self.delay, 1, self.down, 0, 1)

    def stop_trigger_recoil(self):
        """停止扳机压枪"""
        if self.trigger_recoil_active:
            self.trigger_recoil_active = False
            if self._recoil_is_replaying:
                self._recoil_is_replaying = False
            if hasattr(self, 'timer_id2') and self.timer_id2:
                self.time_kill_event(self.timer_id2)
                self.timer_id2 = 0
            self.trigger_recoil_pressed = False
            self.end = True
            self.now_num = 0
            self.now_stage = 0

    def trigger(self):
        self.time_begin_period(1)
        input_shape_weight = self.engine.get_input_shape()[3]
        input_shape_height = self.engine.get_input_shape()[2]
        identify_rect_left = self.screen_center_x - input_shape_weight / 2
        identify_rect_top = self.screen_center_y - input_shape_height / 2
        last_check_time = time.perf_counter()
        check_interval = 0.002
        while self.running:
            current_time = time.perf_counter()
            if current_time - last_check_time < check_interval:
                time.sleep(0.001)
                continue
            last_check_time = current_time
            try:
                aim_targets = self.que_trigger.get_nowait()
            except queue.Empty:
                aim_targets = []
            if len(aim_targets):
                for item in aim_targets:
                    result_center_x, result_center_y, width, height = item
                    x_trigger_offset = self.pressed_key_config['trigger']['x_trigger_offset']
                    y_trigger_offset = self.pressed_key_config['trigger']['y_trigger_offset']
                    x_trigger_scope = self.pressed_key_config['trigger']['x_trigger_scope']
                    y_trigger_scope = self.pressed_key_config['trigger']['y_trigger_scope']
                    left = result_center_x - width / 2
                    top = result_center_y - height / 2
                    left = left + width * x_trigger_offset
                    top = top + height * y_trigger_offset
                    width = width * x_trigger_scope
                    height = height * y_trigger_scope
                    right = left + width
                    bottom = top + height
                    relative_screen_top = identify_rect_top + round(top, 2)
                    relative_screen_left = identify_rect_left + round(left, 2)
                    relative_screen_bottom = identify_rect_top + round(bottom, 2)
                    relative_screen_right = identify_rect_left + round(right, 2)
                    if relative_screen_left < self.screen_center_x < relative_screen_right and relative_screen_top < self.screen_center_y < relative_screen_bottom:
                        continuous_enabled = self.pressed_key_config['trigger'].get('continuous', False)
                        recoil_enabled = self.pressed_key_config['trigger'].get('recoil', False)
                        if continuous_enabled:
                            if not self.continuous_trigger_active and self.aim_key_status:
                                self.continuous_trigger_active = True
                                self.continuous_trigger_thread = Thread(target=self.continuous_trigger_process, args=(recoil_enabled,))
                                self.continuous_trigger_thread.daemon = True
                                self.continuous_trigger_thread.start()
                        elif not self.trigger_status and self.aim_key_status:
                            self.trigger_status = True
                            Thread(target=self.trigger_process, args=(self.pressed_key_config['trigger']['start_delay'], self.pressed_key_config['trigger']['press_delay'], self.pressed_key_config['trigger']['end_delay'], self.pressed_key_config['trigger']['random_delay'], recoil_enabled)).start()
                        break

    def on_status_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['trigger']['status'] = app_data
        print(f"changed to: {self.config['groups'][self.group]['aim_keys'][self.select_key]['trigger']['status']}")

    def on_continuous_trigger_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['trigger']['continuous'] = app_data
        print(f'持续扳机设置为: {app_data}')

    def on_trigger_recoil_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['trigger']['recoil'] = app_data
        print(f'扳机压枪设置为: {app_data}')

    def on_start_delay_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['trigger']['start_delay'] = app_data
        print(f"changed to: {self.config['groups'][self.group]['aim_keys'][self.select_key]['trigger']['start_delay']}")

    def on_long_press_duration_change(self, sender, app_data):
        self.config['groups'][self.group]['long_press_duration'] = app_data
        print(f"changed to: {self.config['groups'][self.group]['long_press_duration']}")

    def on_press_delay_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['trigger']['press_delay'] = app_data
        print(f"changed to: {self.config['groups'][self.group]['aim_keys'][self.select_key]['trigger']['press_delay']}")

    def on_end_delay_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['trigger']['end_delay'] = app_data
        print(f"changed to: {self.config['groups'][self.group]['aim_keys'][self.select_key]['trigger']['end_delay']}")

    def on_random_delay_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['trigger']['random_delay'] = app_data
        print(f"changed to: {self.config['groups'][self.group]['aim_keys'][self.select_key]['trigger']['random_delay']}")

    def on_x_trigger_scope_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['trigger']['x_trigger_scope'] = app_data
        self.update_rect()
        print(f"changed to: {self.config['groups'][self.group]['aim_keys'][self.select_key]['trigger']['x_trigger_scope']}")

    def on_y_trigger_scope_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['trigger']['y_trigger_scope'] = app_data
        self.update_rect()
        print(f"changed to: {self.config['groups'][self.group]['aim_keys'][self.select_key]['trigger']['y_trigger_scope']}")

    def on_x_trigger_offset_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['trigger']['x_trigger_offset'] = app_data
        self.update_rect()
        print(f"changed to: {self.config['groups'][self.group]['aim_keys'][self.select_key]['trigger']['x_trigger_offset']}")

    def on_y_trigger_offset_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['trigger']['y_trigger_offset'] = app_data
        self.update_rect()
        print(f"changed to: {self.config['groups'][self.group]['aim_keys'][self.select_key]['trigger']['y_trigger_offset']}")

    def update_rect(self):
        x_ratio = self.config['groups'][self.group]['aim_keys'][self.select_key]['trigger']['x_trigger_offset']
        y_ratio = self.config['groups'][self.group]['aim_keys'][self.select_key]['trigger']['y_trigger_offset']
        w_ratio = self.config['groups'][self.group]['aim_keys'][self.select_key]['trigger']['x_trigger_scope']
        h_ratio = self.config['groups'][self.group]['aim_keys'][self.select_key]['trigger']['y_trigger_scope']
        x = x_ratio * 50
        y = y_ratio * 100
        w = w_ratio * 50
        h = h_ratio * 100
        dpg.configure_item('small_rect', pmin=[x, y], pmax=[x + w, y + h])


