# -*- coding: utf-8 -*-
"""输入设备管理 Mixin — 从 core.py 提取的设备子系统方法。

设备初始化(init_mouse)、监听线程(start_listen_*)、设备断开(disconnect_device)、
按键屏蔽(unmask_all)、makcu 锁定状态(_init_makcu_locks)。
所有方法操作 self.* 属性，属性由 Valorant.__init__ 创建，通过 mix-in 继承可用。
"""
import time
from threading import Thread, Timer
from queue import Queue
from ctypes import CDLL, windll
import ctypes
from pynput import keyboard, mouse
import kmNet
import pydirectinput
from devices.catbox_wrapper import (
    catbox, init_catbox, catbox_move,
    catbox_left_down, catbox_left_up, catbox_disconnect,
)
from devices.dhz import DHZBOX
from makcu import MakcuController
from pykm2 import i_KM
from util.diagnostics import note_suppressed


class DeviceMixin:
    """输入设备管理 Mixin。

    方法依赖 Valorant.__init__ 中建立的属性：
      self.config / self.move_r / self.move_dll / self.makcu /
      self.aim_key / self.aim_key_status / self.old_pressed_aim_key /
      self.right_pressed / self.left_pressed / self.press_timer 等。
    """

    def start_listen(self):
        self.keyboard_listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        self.mouse_listener = mouse.Listener(on_scroll=self.on_scroll, on_click=self.on_click)
        self.keyboard_listener.start()
        self.mouse_listener.start()

    def start_listen_km_net(self):
        self.keyboard_listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        self.keyboard_listener.start()
        kmNet.monitor(9031)
        self.time_begin_period(1)
        self.km_listen_switch = True
        while self.km_listen_switch:
            if self.key_binding_active:
                # In km_net mode we do not use pynput mouse callbacks,
                # so capture mouse hotkeys from kmNet polling.
                if kmNet.isdown_side1():
                    self.capture_key_press('mouse_x1')
                elif kmNet.isdown_side2():
                    self.capture_key_press('mouse_x2')
                elif kmNet.isdown_middle():
                    self.capture_key_press('mouse_middle')
                elif kmNet.isdown_left():
                    self.capture_key_press('mouse_left')
                elif kmNet.isdown_right():
                    self.capture_key_press('mouse_right')
                time.sleep(0.005)
                continue

            if kmNet.isdown_left():
                if not self.left_pressed:
                    self.left_press()
                if not self.aim_key_status and self.old_pressed_aim_key == '' and ('mouse_left' in self.aim_key):
                    self.refresh_pressed_key_config('mouse_left')
                    self.old_pressed_aim_key = 'mouse_left'
                    self.aim_key_status = True
                    self.reset_dynamic_aim_scope('mouse_left')
                   
            else:
                if self.left_pressed:
                    self.left_release()
                if self.aim_key_status and self.old_pressed_aim_key == 'mouse_left':
                    self.old_pressed_aim_key = ''
                    self.aim_key_status = False
                    self.reset_pid()
            if kmNet.isdown_right():
                if not self.right_pressed:
                    self.right_pressed = True
                if not self.aim_key_status and self.old_pressed_aim_key == '' and ('mouse_right' in self.aim_key):
                    self.refresh_pressed_key_config('mouse_right')
                    self.old_pressed_aim_key = 'mouse_right'
                    self.aim_key_status = True
                    self.reset_dynamic_aim_scope('mouse_right')
              
            else:
                if self.right_pressed:
                    self.right_pressed = False
                if self.aim_key_status and self.old_pressed_aim_key == 'mouse_right':
                    self.old_pressed_aim_key = ''
                    self.aim_key_status = False
                    self.reset_pid()
            if kmNet.isdown_side1():
                if not self.aim_key_status and self.old_pressed_aim_key == '' and ('mouse_x1' in self.aim_key):
                    self.refresh_pressed_key_config('mouse_x1')
                    self.old_pressed_aim_key = 'mouse_x1'
                    self.aim_key_status = True
                    self.reset_dynamic_aim_scope('mouse_x1')
                   
            elif self.aim_key_status and self.old_pressed_aim_key == 'mouse_x1':
                self.old_pressed_aim_key = ''
                self.aim_key_status = False
                self.reset_pid()
            if kmNet.isdown_side2():
                if not self.aim_key_status and self.old_pressed_aim_key == '' and ('mouse_x2' in self.aim_key):
                    self.refresh_pressed_key_config('mouse_x2')
                    self.old_pressed_aim_key = 'mouse_x2'
                    self.aim_key_status = True
                    self.reset_dynamic_aim_scope('mouse_x2')
            elif self.aim_key_status and self.old_pressed_aim_key == 'mouse_x2':
                self.old_pressed_aim_key = ''
                self.aim_key_status = False
                self.reset_pid()
            if kmNet.isdown_middle():
                if not self.aim_key_status and self.old_pressed_aim_key == '' and ('mouse_middle' in self.aim_key):
                    self.refresh_pressed_key_config('mouse_middle')
                    self.old_pressed_aim_key = 'mouse_middle'
                    self.aim_key_status = True
                    self.reset_dynamic_aim_scope('mouse_middle')
            elif self.aim_key_status and self.old_pressed_aim_key == 'mouse_middle':
                self.old_pressed_aim_key = ''
                self.aim_key_status = False
                self.reset_pid()
            time.sleep(0.005)

    def check_long_press(self):
        """检查是否达到长按时间"""
        if self.left_pressed:
            self.left_pressed_long = True

    def left_press(self):
        self.left_pressed = True
        if self.config.get('recoil', {}).get('use_mouse_re_trajectory', False) and getattr(self, 'down_switch', False):
          
            try:
                self._start_mouse_re_recoil()
            except Exception as e:
                print(f'mouse_re轨迹回放启动失败: {e}')
        long_press_duration = self.config['groups'][self.group]['long_press_duration']
        if long_press_duration > 0:
            self.press_timer = Timer(long_press_duration / 1000, self.check_long_press)
            self.press_timer.start()

    def left_release(self):
        self.left_pressed = False
        self.left_pressed_long = False
        self.reset_down_status()
        if self._recoil_is_replaying:
            self._stop_mouse_re_recoil()
        if self.press_timer:
            self.press_timer.cancel()
            self.press_timer = None

    def start_listen_pnmh(self):
        self.keyboard_listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        self.keyboard_listener.start()
        self.pnmh_listen_switch = True
        self.pnmh.Notify_Mouse(63)

        def parse_mouse_button(data):
            btn_map = {4: 'mouse_x1', 5: 'mouse_x2'}
         
            if len(data) >= 3 and data[0] == 7:
                return {'button': btn_map.get(data[1], 'none'), 'action': data[2]}
            btn_map = {1: 'mouse_left', 2: 'mouse_right', 4: 'mouse_middle'}
            return {'button': btn_map.get(data[0], 'none'), 'action': data[1]}
        while self.pnmh_listen_switch:
            ret = self.pnmh.Read_Notify(10)
            if ret:
                data = list(ret)
                data = parse_mouse_button(data)
                if data['button']!= 'none':
                    if data['action'] == 1:
                        if data['button'] == 'mouse_left' and (not self.left_pressed):
                            self.left_press()
                        if not self.aim_key_status and self.old_pressed_aim_key == '':
                            if data['button'] in self.aim_key:
                                self.refresh_pressed_key_config(data['button'])
                                self.old_pressed_aim_key = data['button']
                                self.aim_key_status = True
                    elif data['action'] == 0:
                        if data['button'] == 'mouse_left' and self.left_pressed:
                            self.left_release()
                        if self.aim_key_status and self.old_pressed_aim_key == data['button']:
                            self.old_pressed_aim_key = ''
                            self.aim_key_status = False
                            self.reset_pid()
        self.pnmh.Notify_Mouse(0)

    def _setup_makcu(self):
        """公共 makcu 初始化：连接设备 + 启动发送线程 + 绑定 move_r"""
        if getattr(self, 'makcu', None) is None:
            self.makcu = MakcuController()
        else:
            try:
                self.makcu.disconnect()
            except Exception:
                pass
            self.makcu = MakcuController()
        if self.makcu is not None:
            self._makcu_move_queue = Queue(maxsize=1024)
            self._makcu_send_interval = 0.0015
            self._makcu_last_send_ts = 0.0

            def _makcu_sender_worker():
                last_ts = 0.0
                while not getattr(self, 'end', False):
                    try:
                        dx, dy = self._makcu_move_queue.get(timeout=0.1)
                    except Exception:
                        continue
                    try:
                        while True:
                            nx, ny = self._makcu_move_queue.get_nowait()
                            dx += int(nx)
                            dy += int(ny)
                    except Exception:
                        pass
                    now = time.perf_counter()
                    wait_s = self._makcu_send_interval - (now - last_ts)
                    if wait_s > 0:
                        time.sleep(wait_s)
                    send_ok = False
                    for _ in range(2):
                        try:
                            if self.makcu is not None:
                                self.makcu.move(int(dx), int(dy))
                                send_ok = True
                                break
                        except Exception as e:
                            try:
                                if self.makcu is not None:
                                    self.makcu.disconnect()
                                    time.sleep(0.05)
                                    self.makcu = MakcuController()
                            except Exception as e:
                                note_suppressed('_setup_makcu/reconnect', e)
                                time.sleep(0.05)
                    if not send_ok:
                        time.sleep(0.01)
                    last_ts = time.perf_counter()

            def move_enqueue(x, y):
                if self.makcu is None:
                    return
                try:
                    self._makcu_move_queue.put_nowait((int(x), int(y)))
                except Exception:
                    try:
                        _ = self._makcu_move_queue.get_nowait()
                    except Exception:
                        pass
                    try:
                        self._makcu_move_queue.put_nowait((int(x), int(y)))
                    except Exception:
                        return None
            self.move_r = move_enqueue
            if not hasattr(self, '_makcu_sender_started') or not self._makcu_sender_started:
                t = Thread(target=_makcu_sender_worker, daemon=True)
                t.start()
                self._makcu_sender_started = True
            self._init_makcu_locks()
            return True
        return False

    def start_listen_makcu(self):
        try:
            if self.config['move_method'] == 'makcu':
                self._setup_makcu()
                if self.makcu is not None:
                    self.makcu_listen_switch = True
                    while self.makcu_listen_switch:
                        try:
                            states = getattr(self.makcu, 'button_states', {})
                            left_state = bool(states.get(0, False))
                            right_state = bool(states.get(1, False))
                            middle_state = bool(states.get(2, False))
                            side1_state = bool(states.get(3, False))
                            side2_state = bool(states.get(4, False))
                            if left_state:
                                if not self.left_pressed:
                                    self.left_press()
                                if not self.aim_key_status and self.old_pressed_aim_key == '' and ('mouse_left' in self.aim_key):
                                    self.refresh_pressed_key_config('mouse_left')
                                    self.old_pressed_aim_key = 'mouse_left'
                                    self.aim_key_status = True
                            else:
                                if self.left_pressed:
                                    self.left_release()
                                if self.aim_key_status and self.old_pressed_aim_key == 'mouse_left':
                                    self.old_pressed_aim_key = ''
                                    self.aim_key_status = False
                                    self.reset_pid()
                            if right_state:
                                if not self.right_pressed:
                                    self.right_pressed = True
                                if not self.aim_key_status and self.old_pressed_aim_key == '' and ('mouse_right' in self.aim_key):
                                    self.refresh_pressed_key_config('mouse_right')
                                    self.old_pressed_aim_key = 'mouse_right'
                                    self.aim_key_status = True
                            else:
                                if self.right_pressed:
                                    self.right_pressed = False
                                if self.aim_key_status and self.old_pressed_aim_key == 'mouse_right':
                                    self.old_pressed_aim_key = ''
                                    self.aim_key_status = False
                                    self.reset_pid()
                            if not side1_state or not self.aim_key_status:
                                if self.old_pressed_aim_key == '' and 'mouse_x1' in self.aim_key:
                                    self.refresh_pressed_key_config('mouse_x1')
                                    self.old_pressed_aim_key = 'mouse_x1'
                                    self.aim_key_status = True
                            elif self.aim_key_status and self.old_pressed_aim_key == 'mouse_x1':
                                self.old_pressed_aim_key = ''
                                self.aim_key_status = False
                                self.reset_pid()
                            if not side2_state or (not self.aim_key_status and self.old_pressed_aim_key == '' and ('mouse_x2' in self.aim_key)):
                                self.refresh_pressed_key_config('mouse_x2')
                                self.old_pressed_aim_key = 'mouse_x2'
                                self.aim_key_status = True
                            elif self.aim_key_status and self.old_pressed_aim_key == 'mouse_x2':
                                self.old_pressed_aim_key = ''
                                self.aim_key_status = False
                                self.reset_pid()
                        except Exception as e:
                            print(f'makcu按键状态监听异常: {e}')
                        time.sleep(0.01)
                else:
                    print('makcu未连接')
        except Exception as e:
            print(f'Makcu监听失败: {e}')
            self.makcu = None

    def start_listen_catbox(self):
        """CatBox监听线程 - 使用标准监听方式"""
        print('CatBox监听线程已启动')
        try:
            self.keyboard_listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
            self.keyboard_listener.start()
            self.mouse_listener = mouse.Listener(on_click=self.on_click, on_scroll=self.on_scroll)
            self.mouse_listener.start()
            print('CatBox: 标准键鼠监听已启动')
            while True:
                if not catbox.is_connected:
                    time.sleep(1)
                else:
                    time.sleep(0.01)
        except Exception as e:
            print(f'CatBox监听初始化失败: {e}')

    def start_listen_dhz(self):
        self.keyboard_listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        self.keyboard_listener.start()
        self.dhz.monitor(7654)
        self.time_begin_period(1)
        self.dhz_listen_switch = True
        while self.dhz_listen_switch:
            if self.dhz.isdown_left():
                if not self.left_pressed:
                    self.left_press()
                if not self.aim_key_status and self.old_pressed_aim_key == '' and ('mouse_left' in self.aim_key):
                    self.refresh_pressed_key_config('mouse_left')
                    self.old_pressed_aim_key = 'mouse_left'
                    self.aim_key_status = True
            else:
                if self.left_pressed:
                    self.left_release()
                if self.aim_key_status and self.old_pressed_aim_key == 'mouse_left':
                    self.old_pressed_aim_key = ''
                    self.aim_key_status = False
                    self.reset_pid()
            if self.dhz.isdown_right():
                if not self.right_pressed:
                    self.right_pressed = True
                if not self.aim_key_status and self.old_pressed_aim_key == '' and ('mouse_right' in self.aim_key):
                    self.refresh_pressed_key_config('mouse_right')
                    self.old_pressed_aim_key = 'mouse_right'
                    self.aim_key_status = True
            else:
                if self.right_pressed:
                    self.right_pressed = False
                if self.aim_key_status and self.old_pressed_aim_key == 'mouse_right':
                    self.old_pressed_aim_key = ''
                    self.aim_key_status = False
                    self.reset_pid()
            if self.dhz.isdown_side1():
                if not self.aim_key_status and self.old_pressed_aim_key == '' and ('mouse_x1' in self.aim_key):
                    self.refresh_pressed_key_config('mouse_x1')
                    self.old_pressed_aim_key = 'mouse_x1'
                    self.aim_key_status = True
            elif self.aim_key_status and self.old_pressed_aim_key == 'mouse_x1':
                self.old_pressed_aim_key = ''
                self.aim_key_status = False
                self.reset_pid()
            if self.dhz.isdown_side2():
                if not self.aim_key_status and self.old_pressed_aim_key == '' and ('mouse_x2' in self.aim_key):
                    self.refresh_pressed_key_config('mouse_x2')
                    self.old_pressed_aim_key = 'mouse_x2'
                    self.aim_key_status = True
            elif self.aim_key_status and self.old_pressed_aim_key == 'mouse_x2':
                self.old_pressed_aim_key = ''
                self.aim_key_status = False
                self.reset_pid()
            if self.dhz.isdown_middle():
                if not self.aim_key_status and self.old_pressed_aim_key == '':
                    if 'mouse_middle' in self.aim_key:
                        self.refresh_pressed_key_config('mouse_middle')
                        self.old_pressed_aim_key = 'mouse_middle'
                        self.aim_key_status = True
            elif self.aim_key_status and self.old_pressed_aim_key == 'mouse_middle':
                self.old_pressed_aim_key = ''
                self.aim_key_status = False
                self.reset_pid()
            time.sleep(0.001)
        self.dhz.RECEIVER_FLAG = False

    def stop_listen(self):
        if self.keyboard_listener is not None and self.keyboard_listener.is_alive():
            self.keyboard_listener.stop()
            self.keyboard_listener.join()
        if self.mouse_listener is not None and self.mouse_listener.is_alive():
            self.mouse_listener.stop()
            self.mouse_listener.join()
        self.km_listen_switch = False
        if self.dhz is not None and self.dhz.RECEIVER_FLAG:
            self.dhz.RECEIVER_FLAG = False
        self.dhz_listen_switch = False
        self.pnmh_listen_switch = False
        self.makcu_listen_switch = False

    def disconnect_device(self):
        try:
            if getattr(self, 'keyboard_listener', None) is not None and self.keyboard_listener.is_alive():
                try:
                    self.keyboard_listener.stop()
                    self.keyboard_listener.join()
                except Exception:
                    pass
            if getattr(self, 'mouse_listener', None) is not None and self.mouse_listener.is_alive():
                try:
                    self.mouse_listener.stop()
                    self.mouse_listener.join()
                except Exception:
                    pass
            self.km_listen_switch = False
            self.dhz_listen_switch = False
            self.pnmh_listen_switch = False
            self.makcu_listen_switch = False
            self.unmask_all()
            move_method = self.config.get('move_method')
            if move_method == 'makcu':
                if getattr(self, 'makcu', None) is not None:
                    try:
                        try:
                            self.makcu.disconnect()
                        except Exception as e:
                            print('断开Makcu失败: ' + f'{e}')
                    finally:
                        if hasattr(self, '_makcu_move_queue') and self._makcu_move_queue is not None:
                            try:
                                while True:
                                    self._makcu_move_queue.get_nowait()
                            except Exception:
                                pass
                        self.makcu = None
            elif move_method == 'dhz':
                if getattr(self, 'dhz', None) is not None:
                    try:
                        self.dhz.monitor(0)
                    except Exception:
                        pass
                    self.dhz.RECEIVER_FLAG = False
            elif move_method == 'km_net':
                try:
                    if hasattr(kmNet, 'monitor'):
                        try:
                            kmNet.monitor(0)
                        except Exception:
                            pass
                    if hasattr(kmNet, 'unmask_all'):
                        kmNet.unmask_all()
                except Exception as e:
                    print('断开KM Net失败: ' + f'{e}')
            elif move_method == 'catbox':
                try:
                    catbox_disconnect()
                except Exception as e:
                    print('断开CatBox失败: ' + f'{e}')
            elif move_method == 'pnmh':
                if getattr(self, 'pnmh', None) is not None:
                    try:
                        self.pnmh.Lock_Mouse(0)
                        self.pnmh.Notify_Mouse(0)
                    except Exception:
                        pass
            self.left_pressed = False
            self.right_pressed = False
            self.aim_key_status = False
            self.old_pressed_aim_key = ''
        except Exception as e:
            print('断开设备失败: ' + f'{e}')

    def unmask_all(self):
        """解除所有屏蔽"""
        if self.config['move_method'] == 'makcu':
            if self.makcu is not None:
                try:
                    self.makcu.lock_ml(0)
                    self.makcu.lock_mr(0)
                    self.makcu.lock_mm(0)
                    self.makcu.lock_ms1(0)
                    self.makcu.lock_ms2(0)
                    self.makcu.lock_mx(0)
                    self.makcu.lock_my(0)
                except Exception as e:
                    print(f'解除Makcu屏蔽失败: {e}')
        elif self.config['move_method'] == 'dhz':
            if self.dhz is not None:
                self.dhz.mask_left(0)
                self.dhz.mask_right(0)
                self.dhz.mask_middle(0)
                self.dhz.mask_side1(0)
                self.dhz.mask_side2(0)
                self.dhz.mask_x(0)
                self.dhz.mask_y(0)
                self.dhz.mask_wheel(0)
        elif self.config['move_method'] == 'km_net':
            kmNet.unmask_all()
        elif self.config['move_method'] == 'pnmh' and self.pnmh is not None:
            self.pnmh.Lock_Mouse(0)


    def init_mouse(self):
        try:
            if self.config['move_method'] == 'makcu':
                if not self._setup_makcu():
                    print('makcu未连接')
        except Exception as e:
            print(f'Makcu初始化失败: {e}')
            self.makcu = None
        if self.config['move_method'] == 'km_box_a':
            print('km_box_a模式')
            km_box_pid = int(self.config['km_box_pid'], 16)
            km_box_vid = int(self.config['km_box_vid'], 16)
            self.move_dll = CDLL('./km.dll')
            res = self.move_dll.KM_init(ctypes.c_ushort(km_box_vid), ctypes.c_ushort(km_box_pid))
            print('km_box_a初始化:{}'.format(res))
            self.move_r = self.move_dll.KM_move
        if self.config['move_method'] == 'send_input':
            print('send_input模式')
            self.move_dll = None
            self.move_r = pydirectinput.moveRel
        if self.config['move_method'] == 'logitech':
            print('logitech模式')
            self.move_dll = CDLL('./logitech.dll')
            self.move_r = self.move_dll.moveR
        if self.config['move_method'] == 'km_net':
            print('km_net模式')
            km_ip = str(self.config.get('km_net_ip', '')).strip()
            km_uuid = str(self.config.get('km_net_uuid', '')).strip()
            km_port = str(self.config.get('km_net_port', '')).strip()
            try:
                result = kmNet.init(km_ip, km_port, km_uuid)
            except Exception as e:
                print(f'初始化失败: kmNet.init异常={e}, ip={km_ip}, port={km_port}, uuid={km_uuid}')
                result = -9999
            if result == 0:
                print('初始化成功')
                self.move_dll = None
                self.move_r = kmNet.move
                if self.config['mask_left']:
                    kmNet.mask_left(1)
                if self.config['mask_right']:
                    kmNet.mask_right(1)
                if self.config['mask_middle']:
                    kmNet.mask_middle(1)
                if self.config['mask_side1']:
                    kmNet.mask_side1(1)
                if self.config['mask_side2']:
                    kmNet.mask_side2(1)
                if self.config['mask_x']:
                    kmNet.mask_x(1)
                if self.config['mask_y']:
                    kmNet.mask_y(1)
                if self.config['mask_wheel']:
                    kmNet.mask_wheel(1)
            else:
                print(f'初始化失败: code={result}, ip={km_ip}, port={km_port}, uuid={km_uuid}')
                # Fallback to local move backend so control path can still be verified.
                self.move_dll = None
                self.move_r = pydirectinput.moveRel
        if self.config['move_method'] == 'dhz':
            print('dhz模式')
            self.dhz = DHZBOX(self.config['dhz_ip'], self.config['dhz_port'], self.config['dhz_random'])
            if self.config['mask_left']:
                self.dhz.mask_left(1)
            if self.config['mask_right']:
                self.dhz.mask_right(1)
            if self.config['mask_middle']:
                self.dhz.mask_middle(1)
            if self.config['mask_side1']:
                self.dhz.mask_side1(1)
            if self.config['mask_side2']:
                self.dhz.mask_side2(1)
            if self.config['mask_x']:
                self.dhz.mask_x(1)
            if self.config['mask_y']:
                self.dhz.mask_y(1)
            if self.config['mask_wheel']:
                self.dhz.mask_wheel(1)
            self.move_r = self.dhz.move
        if self.config['move_method'] == 'pnmh':
            if self.pnmh is not None and self.pnmh.IsOpen():
                self.pnmh.Close()
                del self.pnmh
            self.pnmh = i_KM()
            ret = self.pnmh.OpenDevice(self.config['km_com'])
            if not ret:
                print('叛逆魔盒未连接')
            else:
                print('叛逆魔盒已连接')
                print('型号:', chr(self.pnmh.GetModel() + 64))
                print('版本:', self.pnmh.GetVersion())
                print('序列号:', self.pnmh.GetChipID())
                print('空间大小:', self.pnmh.GetStorageSize())
                self.pnmh.SetWaitRespon(False)
            self.move_r = self.pnmh.MoveR
        if self.config['move_method'] == 'catbox':
            print('catbox模式')
            result = init_catbox(self.config['catbox_ip'], self.config['catbox_port'], self.config['catbox_uuid'])
            if result:
                print('CatBox初始化成功')
                self.move_dll = None
                self.move_r = catbox_move
                if self.config['mask_left']:
                    catbox.mask_left(1)
                if self.config['mask_right']:
                    catbox.mask_right(1)
                if self.config['mask_middle']:
                    catbox.mask_middle(1)
                if self.config['mask_side1']:
                    catbox.mask_side1(1)
                if self.config['mask_side2']:
                    catbox.mask_side2(1)
                if self.config['mask_x']:
                    catbox.mask_x(1)
                if self.config['mask_y']:
                    catbox.mask_y(1)
                if self.config['mask_wheel']:
                    catbox.mask_wheel(1)
            else:
                print('CatBox初始化失败')
        if self.config['move_method'] == 'dhz':
            listen_thread = Thread(target=self.start_listen_dhz)
        elif self.config['move_method'] == 'km_net':
            listen_thread = Thread(target=self.start_listen_km_net)
        elif self.config['move_method'] == 'pnmh':
            listen_thread = Thread(target=self.start_listen_pnmh)
        elif self.config['move_method'] == 'makcu':
            listen_thread = Thread(target=self.start_listen_makcu)
        elif self.config['move_method'] == 'catbox':
            listen_thread = Thread(target=self.start_listen_catbox)
        else:
            listen_thread = Thread(target=self.start_listen)
        listen_thread.setDaemon(True)
        listen_thread.start()


    def _init_makcu_locks(self):
        """初始化 makcu 的按钮和轴锁定状态"""
        if self.makcu is None:
            return
        try:
            if self.config['mask_left']:
                self.makcu.lock_ml(1)
            if self.config['mask_right']:
                self.makcu.lock_mr(1)
            if self.config['mask_middle']:
                self.makcu.lock_mm(1)
            if self.config['mask_side1']:
                self.makcu.lock_ms1(1)
            if self.config['mask_side2']:
                self.makcu.lock_ms2(1)
            if self.config['mask_x']:
                self.makcu.lock_mx(1)
            if self.config['mask_y']:
                self.makcu.lock_my(1)
            if self.config['mask_wheel']:
                return
        except Exception as e:
            print(f'初始化Makcu锁定状态失败: {e}')

