import copy
import ctypes
import json
import math
from devices.catbox_wrapper import catbox, init_catbox, catbox_move, catbox_left_down, catbox_left_up, catbox_disconnect
import os
import queue
import random
import string
import sys
import time
import traceback
from ctypes import CDLL, CFUNCTYPE, c_void_p, windll
from queue import Queue
from threading import Thread, Timer
from inference.decode_model import build_model
import cv2
import dearpygui.dearpygui as dpg
import kmNet
import numpy as np
from aim.crosshair_tracker import CrosshairTracker
from devices.flashbang_handler import FlashbangHandler
from settings import config_manager as cfgmgr
import pydirectinput
pydirectinput.PAUSE = 0
pydirectinput.FAILSAFE = False
import win32api
import win32con
import win32gui
from PIL import Image
from pynput import keyboard, mouse
from pyclick import HumanCurve
import threading
from concurrent.futures import ThreadPoolExecutor
from aim.aim_pipeline import AimPipeline
from util.diagnostics import note_suppressed
from .runtime import (
    BAR_HEIGHT,
    SHADOW_OFFSET,
    TENSORRT_AVAILABLE,
    TensorRTInferenceEngine,
    UPDATE_TIME,
    VERSION,
    check_tensorrt_availability,
    create_gradient_image,
    ensure_engine_from_memory,
)

def detect_inference_devices():
    """
    自动检测系统可用的推理设备
    返回设备列表和设备信息字典
    """
    devices = []
    device_info = {}
    
    try:
        import onnxruntime as ort
        available_providers = ort.get_available_providers()
        
        # 检测CPU
        if 'CPUExecutionProvider' in available_providers:
            devices.append('CPU')
            device_info['CPU'] = {
                'provider': 'CPUExecutionProvider',
                'description': 'CPU推理 (默认)',
                'performance': '标准'
            }
        
        # 检测DirectML (Windows GPU)
        if 'DmlExecutionProvider' in available_providers:
            devices.append('DML')
            device_info['DML'] = {
                'provider': 'DmlExecutionProvider',
                'description': 'DirectML GPU推理 (Windows)',
                'performance': '高性能'
            }
        
        # 检测CUDA
        if 'CUDAExecutionProvider' in available_providers:
            devices.append('CUDA')
            device_info['CUDA'] = {
                'provider': 'CUDAExecutionProvider',
                'description': 'CUDA GPU推理 (NVIDIA)',
                'performance': '最高性能'
            }
        
        # 检测TensorRT
        if 'TensorrtExecutionProvider' in available_providers:
            devices.append('TensorRT')
            device_info['TensorRT'] = {
                'provider': 'TensorrtExecutionProvider',
                'description': 'TensorRT GPU推理 (NVIDIA)',
                'performance': '极致性能'
            }
        
        # 如果没有检测到任何设备，使用CPU作为后备
        if not devices:
            devices = ['CPU']
            device_info['CPU'] = {
                'provider': 'CPUExecutionProvider',
                'description': 'CPU推理 (后备)',
                'performance': '标准'
            }
        
        print(f"检测到可用推理设备: {devices}")
        return devices, device_info
        
    except Exception as e:
        print(f"推理设备检测失败: {e}")
        # 返回默认设备
        return ['CPU'], {'CPU': {'provider': 'CPUExecutionProvider', 'description': 'CPU推理 (默认)', 'performance': '标准'}}

from settings.buff import Buff_Single, Buff_User
from devices.dhz import DHZBOX
from util.gui_handlers import ConfigChangeHandler, ConfigItemGroup
from util.profiler import FrameProfiler
from inference.infer_class import OnnxRuntimeDmlEngine
from inference.infer_function import nms, nms_v8, read_img
from inference.v11onnx_support import (
    ModelValidationError,
    build_ort_runtime_components,
    discover_v11onnx_model,
    get_default_runtime_config,
    infer_model_variant_from_path,
    resolve_runtime_config,
    should_use_v11onnx,
    validate_v11onnx_model,
)

from makcu import MakcuController
import socket
from devices.obs import OBSVideoStream
from pykm2 import i_KM
from devices.screenshot_manager import ScreenshotManager
try:
    from webui.server import start_web_server
except ImportError:
    start_web_server = None


print('')
print('####### ######  ####  ####  ### \n   #    #      #    # #   # #   # \n   #    #####  #    # ####  #   # \n   #    #      #    # #  #  #   # \n   #    ######  ####  #   # ###  \n                                        \n')

from pynput.keyboard import Key, KeyCode
from util.function import key2str

from .mixins.devices import DeviceMixin
from .mixins.inference import InferenceMixin
from .mixins.trigger import TriggerMixin
from .mixins.config import ConfigMixin
from .mixins.crosshair_ui import CrosshairUIMixin
from .mixins.gui import GUIMixin
from .mixins.mousere import MouseReMixin
from .mixins.gameconfig import GameConfigMixin
from .mixins.mask import MouseMaskMixin
from .mixins.flash import FlashbangMixin
from .mixins.keybind import KeyBindMixin
from .mixins.infercfg import InferConfigMixin
from .mixins.systemcfg import SystemConfigMixin
from .mixins.aimcfg import AimConfigMixin
from .mixins.pidtracker import PidTrackerMixin
from .mixins.verify import VerifyMixin
from .mixins.display import DisplayMixin
from .mixins.persist import ConfigPersistMixin
from .mixins.input import InputListenerMixin
from .mixins.perception import PerceptionMixin

class Valorant(VerifyMixin, DeviceMixin, InputListenerMixin, InferenceMixin, PerceptionMixin, TriggerMixin, ConfigMixin, ConfigPersistMixin, CrosshairUIMixin, DisplayMixin, GUIMixin, MouseReMixin, GameConfigMixin, MouseMaskMixin, FlashbangMixin, KeyBindMixin, InferConfigMixin, SystemConfigMixin, AimConfigMixin, PidTrackerMixin):
    def __init__(self):
        self.is_v8_checkbox = None
        self.is_trt_checkbox = None
        self.press_timer = None
        self.auto_y_checkbox = None
        self.use_crosshair_checkbox = None
        self.right_down_checkbox = None
        self.down_switch = False
        self.decimal_x = 0
        self.decimal_y = 0
        self.end = False
        self.left_pressed = False
        self.left_pressed_long = False
        self.right_pressed = False
        self.number_input = None
        self.x_input = None
        self.y_input = None
        self.picked_stage = 0
        self.stages_combo = None
        self.add_gun_name = ''
        self.picked_gun = ''
        self.guns_combo = None
        self.add_game_name = ''
        self.games_combo = None
        self.timer_id2 = 0
        self.delay = 10
        self.now_num = 0
        self.now_stage = 0
        self.target_priority = {'distance_scoring_weight': 0.6, 'center_scoring_weight': 0.4, 'size_scoring_weight': 0.3, 'small_target_boost': 2.0, 'small_target_threshold': 0.01, 'medium_target_threshold': 0.05, 'medium_target_boost': 1.5}
        self.last_flashbang_time = 0
        self.flashbang_cooldown = 1.0
        self.current_yaw = 0
        self.is_turning_back = False
        self.turn_back_start_time = 0
        self.flashbang_actual_move_x = 0
        self.flashbang_actual_move_y = 0
        self._flashbang = None  # 延迟初始化，需要 move_r
        self._dopa_warning_shown = False
        self.fps = 0
        self.kalman_filter = None
        self.debug_prediction = False  # 添加预测调试开关
        self.aim_pipeline = AimPipeline()
        self.showed = False
        self.km_listen_switch = False
        self.dhz_listen_switch = False
        self.pnmh_listen_switch = False
        self.makcu_listen_switch = False
        self.move_r = None
        self.move_dll = None
        self.add_key_name = ''
        self.add_group_name = ''
        self.selected_items = []
        self.checkboxes = []
        self.checkbox_group_tag = None
        
        # 按键绑定功能相关变量
        self.key_binding_active = False
        self.key_binding_callback = None
        self.key_binding_tag = None
        self.key_binding_button_tag = None
        self.key_binding_status_tag = None
        # when binding mode starts, record time so we can ignore the triggering click
        self.key_binding_start_time = 0.0
        self.one_click_match_button_tag = None
        self.obs_ip_input = None
        self.obs_port_input = None
        self.obs_fps_slider = None
        self.identify_rect_top = None
        self.identify_rect_left = None
        self.engine = None
        self._cached_model_area = None
        self.running = False
        self.decrypted_model_data = None
        self.original_model_path = None
        self.start_button_tag = None
        self.select_key = ''
        self.end_delay_input = None
        self.press_delay_input = None
        self.start_delay_input = None
        self.random_delay_input = None
        self.x_trigger_scope_input = None
        self.y_trigger_scope_input = None
        self.x_trigger_offset_input = None
        self.y_trigger_offset_input = None
        self.status_input = None
        self.continuous_trigger_input = None
        self.trigger_recoil_input = None
        self.deadzone_input = None
        self.history_size_input = None
        self.output_scale_x_input = None
        self.output_scale_y_input = None
        self.uniform_threshold_input = None
        self.min_velocity_threshold_input = None
        self.max_velocity_threshold_input = None
        self.compensation_factor_input = None
        self.fov_angle_input = None
        self.distance_weight_input = None
        self.base_step_input = None
        self.smoothing_factor_input = None
        self.aim_bot_scope_input = None
        self.min_position_offset_input = None
        self.aim_bot_position_slider = None
        self.aim_bot_position2_slider = None
        self.pid_error_filter_alpha_slider = None
        self.pid_vel_filter_alpha_slider = None
        self.tracker_enabled_checkbox = None
        self.tracker_match_thresh_slider = None
        self.tracker_track_buffer_slider = None
        self.target_sticky_pixels_slider = None
        self.target_lock_ms_slider = None
        self.large_target_threshold_slider = None
        self.large_target_boost_slider = None
        self.kalman_enabled_checkbox = None
        self.kalman_predict_frames_slider = None
        self.kalman_predict_gain_slider = None
        self.min_lead_speed_slider = None
        self.max_lead_slider = None
        self.lead_smooth_slider = None
        self.target_id_lock_checkbox = None
        self.class_aim_combo = None
        self.dynamic_scope_enabled_input = None
        self.dynamic_scope_min_scope_input = None
        self.dynamic_scope_shrink_ms_input = None
        self.dynamic_scope_recover_ms_input = None
        self.current_selected_class = '0'
        self.class_priority_input = None
        self.infer_model_input = None
        self.confidence_threshold_slider = None
        self.iou_t_slider = None
        self.key_tag = None
        self.move_group_tag = None
        self.window_tag = None
        self.old_refreshed_aim_key = ''
        self._model_validation_cache = {}
        self.config, self.aim_keys_dist, self.aim_key, self.group = self.build_config()
        #self.config, self.aim_keys_dist, self.aim_key, self.group
        
        # 自动检测推理设备
        self.available_devices, self.device_info = detect_inference_devices()
        
        # 设置默认推理设备
        if 'inference_device' not in self.config:
            # 优先选择性能更高的设备
            preferred_devices = ['TensorRT', 'CUDA', 'DML', 'CPU']
            for device in preferred_devices:
                if device in self.available_devices:
                    self.config['inference_device'] = device
                    break
        
        if 'small_target_enhancement' not in self.config:
            self.config['small_target_enhancement'] = {'enabled': True, 'boost_factor': 2.0, 'threshold': 0.01, 'medium_threshold': 0.05, 'medium_boost': 1.5, 'smooth_enabled': True, 'smooth_frames': 5, 'adaptive_nms': True}
        if 'crosshair_color_lock' not in self.config or not isinstance(self.config.get('crosshair_color_lock'), dict):
            self.config['crosshair_color_lock'] = {'enabled': False, 'roi_width': 200, 'roi_height': 200, 'hsv_ranges': [{'h_min': 0, 'h_max': 179, 's_min': 0, 's_max': 255, 'v_min': 0, 'v_max': 255}], 'active_index': 0, 'show_crosshair': True, 'show_lock_box': True, 'min_area': 12, 'last_rgb': [0, 0, 0], 'pull_k': 0.12, 'pull_max_speed': 6.0, 'pull_deadzone': 1.0, 'ema_smooth': 0.4}
        crosshair_cfg = self.config['crosshair_color_lock']
        if isinstance(crosshair_cfg, dict):
            crosshair_cfg.setdefault('pull_k', 0.12)
            crosshair_cfg.setdefault('pull_max_speed', 6.0)
            crosshair_cfg.setdefault('pull_deadzone', 1.0)
            crosshair_cfg.setdefault('ema_smooth', 0.4)
        self.crosshair_preview_width = int(crosshair_cfg.get('preview_width', 320))
        self.crosshair_preview_height = int(crosshair_cfg.get('preview_height', 320))
        self.crosshair_preview_texture_tag = 'crosshair_preview_texture'
        # 准星追踪器（独立模块）
        self._crosshair_tracker = CrosshairTracker()
        self._crosshair_future = None
        self.crosshair_pick_mode = False
        self.crosshair_use_pending = False
        self.crosshair_pending_hsv = None
        self.crosshair_pending_rgb = None
        self.crosshair_color_group_combo = None
        self.crosshair_delete_color_button = None
        self.crosshair_h_min_slider = None
        self.crosshair_h_max_slider = None
        self.crosshair_s_min_slider = None
        self.crosshair_s_max_slider = None
        self.crosshair_v_min_slider = None
        self.crosshair_v_max_slider = None
        self.crosshair_rgb_text = None
        self.crosshair_pick_status_text = None
        auto_dpi_scale = self.get_system_dpi_scale()
        config_dpi_scale = self.config.get('gui_dpi_scale', 0.0)
        self.dpi_scale = config_dpi_scale if config_dpi_scale > 0 else auto_dpi_scale
        base_width, base_height = (720, 750)
        self.gui_window_width = int(base_width * self.dpi_scale)
        self.gui_window_height = int(base_height * self.dpi_scale)
        self.scaled_bar_height = int(2 * self.dpi_scale)
        self.scaled_sidebar_width = int(60 * self.dpi_scale)
        self.scaled_font_size_main = int(12 * self.dpi_scale)
        self.scaled_font_size_custom = int(14 * self.dpi_scale)
        self.scaled_width_small = int(50 * self.dpi_scale)
        self.scaled_width_60 = int(60 * self.dpi_scale)
        self.scaled_width_medium = int(80 * self.dpi_scale)
        self.scaled_width_normal = int(100 * self.dpi_scale)
        self.scaled_width_large = int(120 * self.dpi_scale)
        self.scaled_width_xlarge = int(200 * self.dpi_scale)
        self.scaled_height_normal = int(100 * self.dpi_scale)
        if not TENSORRT_AVAILABLE:
            trt_used = False
            for group_name, group_data in self.config['groups'].items():
                if group_data.get('is_trt', False):
                    trt_used = True
                    group_data['is_trt'] = False
                    if group_data['infer_model'].endswith('.engine'):
                        onnx_path = group_data.get('original_infer_model')
                      
                        if onnx_path and os.path.exists(onnx_path):
                            group_data['infer_model'] = onnx_path
                        else:
                            possible_onnx = os.path.splitext(group_data['infer_model'])[0] + '.onnx'
                            if os.path.exists(possible_onnx):
                                group_data['infer_model'] = possible_onnx
        self.config_handler = ConfigChangeHandler(self.config, None)
        self.config_handler.register_context_provider('group', lambda: self.group)
        self.config_handler.register_context_provider('key', lambda: self.select_key)
        self._init_config_handlers()
        self.init_target_priority()
        self._sensitivity_display_initialized = False
        self.mouse_listener = None
        self.keyboard_listener = None
        self.old_pressed_aim_key = ''
        self.que_aim = Queue(maxsize=1)
        self.que_trigger = Queue(maxsize=1)
        self.aim_key_status = False
        self.aim_bot = CFUNCTYPE(c_void_p, c_void_p, c_void_p, c_void_p, c_void_p, c_void_p)(self.aim_bot_func)
        self.down = CFUNCTYPE(c_void_p, c_void_p, c_void_p, c_void_p, c_void_p, c_void_p)(self.down_func)
        self.timer_id = 0
        self.pressed_key = []
        self.time_set_event = windll.winmm.timeSetEvent
        self.time_kill_event = windll.winmm.timeKillEvent
        self.time_begin_period = windll.winmm.timeBeginPeriod
        self.time_end_period = windll.winmm.timeEndPeriod
        self.screen_width, self.screen_height = self.get_dpi_aware_screen_size()
        self.screen_center_x = int(self.screen_width / 2)
        self.screen_center_y = int(self.screen_height / 2)
        self.screenshot_manager = None
        if len(self.aim_key) > 0:
            self.select_key = self.aim_key[0]
            self.pressed_key_config = self.aim_keys_dist[self.aim_key[0]]
        self.aim_pid = self.aim_pipeline.pid
        self.control_mode = 'idle'
        self.last_target_count = 0
        self.last_target_count_by_class = {}
        self.target_switch_time = 0
        self.is_waiting_for_switch = False
        self._dynamic_scope = {'value': 0, 'phase': 'idle', 'last_ms': time.time() * 1000.0}
        self._dynamic_scope_lock_active_prev = False
        self.refresh_controller_params()
        self.trigger_status = False
        self.continuous_trigger_active = False
        self.continuous_trigger_thread = None
        self.trigger_recoil_active = False
        self.trigger_recoil_thread = None
        self.trigger_recoil_pressed = False
        self.picked_game = self.config['picked_game']
      
        self.games = list(self.config['games'].keys())
        self.dhz = None
        self.pnmh = None
        self.makcu = None
        self.temp_aim_bot_position = 0.0
        self.game_sensitivity = self.config.get('game_sensitivity', 1.0)
        self.mouse_dpi = self.config.get('mouse_dpi', 800)
        self.base_sensitivity = 1.0
        self.target_history = {}
        self.target_history_max_frames = 5
        # 仅在Web功能启用时启动Web服务器
        if start_web_server is not None:
            if self.config.get('enable_web_server', False):
                start_web_server(self)
            else:
                print('[Web控制面板] Web功能未启用')
        else:
            print('[Web控制面板] 未找到 web/server.py，无法启动Web服务。')
        self.change = self._change_callback
        self.verified = False
        self._save_timer = None
        self.frame_profiler = FrameProfiler()
        if 'recoil' not in self.config:
            self.config['recoil'] = {'use_mouse_re_trajectory': False, 'replay_speed': 1.0, 'pixel_enhancement_ratio': 1.0, 'mapping': {}}
        else:
            self.config['recoil'].setdefault('use_mouse_re_trajectory', False)
            self.config['recoil'].setdefault('replay_speed', 1.0)
            self.config['recoil'].setdefault('pixel_enhancement_ratio', 1.0)
            self.config['recoil'].setdefault('mapping', {})
            if not isinstance(self.config['recoil']['mapping'], dict):
                print('[修复] recoil.mapping类型错误，重置为空字典')
                self.config['recoil']['mapping'] = {}
        self._current_mouse_re_points = None
        self._recoil_replay_thread = None
        self._recoil_is_replaying = False
        self.mouse_re_picked_game = self.config.get('picked_game', '')
        self.mouse_re_picked_gun = ''
        self.mouse_re_games_combo = None
        self.mouse_re_guns_combo = None


    def _change_callback(self, path, value):
        if path == 'inference':
            if value == 'start' and (not self.running):
                if not self.verified:
                    print('验证失败，无法启动推理')
                    return
                self.running = True
                self.go()
                return
            if value == 'stop' and self.running:
                self.running = False
                if self.timer_id!= 0:
                    self.time_kill_event(self.timer_id)
                    self.timer_id = 0
                if self.timer_id2!= 0:
                    self.time_kill_event(self.timer_id2)
                    self.timer_id2 = 0
                self.close_screenshot()
                self.disconnect_device()
            return None
        parts = path.split('.')
        value_changed = False
        if len(parts) == 1:
            method = getattr(self, f'on_{parts[0]}_change', None)
            if callable(method):
                method(None, value)
            elif parts[0] not in self.config or self.config[parts[0]]!= value:
                self.config[parts[0]] = value
                value_changed = True
        elif len(parts) == 3 and parts[0] == 'groups':
            group, key = (parts[1], parts[2])
            method = getattr(self, f'on_{key}_change', None)
            if callable(method):
                method(None, value)
            else:
                if group not in self.config['groups']:
                    self.config['groups'][group] = {}
                if key not in self.config['groups'][group] or self.config['groups'][group][key]!= value:
                    self.config['groups'][group][key] = value
                     
                    value_changed = True
        elif len(parts) >= 5 and parts[0] == 'groups' and (parts[2] == 'aim_keys'):
            group, aim_key, param = (parts[1], parts[3], parts[4])
            if group not in self.config['groups']:
                self.config['groups'][group] = {}
            if 'aim_keys' not in self.config['groups'][group]:
                       
                self.config['groups'][group]['aim_keys'] = {}
            if aim_key not in self.config['groups'][group]['aim_keys']:
                self.config['groups'][group]['aim_keys'][aim_key] = {}
            if param == 'trigger' and len(parts) == 6:
                trigger_param = parts[5]
                if 'trigger' not in self.config['groups'][group]['aim_keys'][aim_key]:
                    self.config['groups'][group]['aim_keys'][aim_key]['trigger'] = {'status': False, 'continuous': False, 'recoil': False, 'start_delay': 0, 'press_delay': 1, 'end_delay': 0, 'random_delay': 0, 'x_trigger_scope': 1.0, 'y_trigger_scope': 1.0, 'x_trigger_offset': 0.0, 'y_trigger_offset': 0.0}
                if trigger_param not in self.config['groups'][group]['aim_keys'][aim_key]['trigger'] or self.config['groups'][group]['aim_keys'][aim_key]['trigger'][trigger_param]!= value:
                    self.config['groups'][group]['aim_keys'][aim_key]['trigger'][trigger_param] = value
                  
                    value_changed = True
            elif param not in self.config['groups'][group]['aim_keys'][aim_key] or self.config['groups'][group]['aim_keys'][aim_key][param]!= value:
                self.config['groups'][group]['aim_keys'][aim_key][param] = value
                    
                value_changed = True
            self.refresh_pressed_key_config(aim_key)
        else:
            obj = self.config
            for i, p in enumerate(parts[:(-1)]):
                if p not in obj:
                    obj[p] = {}
                obj = obj[p]
            last_part = parts[(-1)]
            if last_part not in obj or obj[last_part]!= value:
                obj[last_part] = value
                value_changed = True
        if value_changed:
            print(f'配置已更改: {path} = {value}')

    def down_func(self, u_timer_id, u_msg, dw_user, dw1, dw2):
        """原有的压枪逻辑，与mouse_re并存"""
        if self.config.get('recoil', {}).get('use_mouse_re_trajectory', False):
      
            return
        left_press_valid = self.left_pressed and self.down_switch
        trigger_press_valid = self.trigger_recoil_pressed
        if left_press_valid or trigger_press_valid:
            if not self.end:
                if self.config['groups'][self.group]['right_down'] and (not self.right_pressed):
                    return
                if self.now_num >= self.config['games'][self.picked_game][self.picked_gun][self.now_stage]['number']:
                    self.now_num = 0
                    if self.now_stage + 1 < len(self.config['games'][self.picked_game][self.picked_gun]):
                        self.now_stage = self.now_stage + 1
                if self.now_stage + 1 <= len(self.config['games'][self.picked_game][self.picked_gun]):
                    x = self.config['games'][self.picked_game][self.picked_gun][self.now_stage]['offset'][0]
                   
                    y = self.config['games'][self.picked_game][self.picked_gun][self.now_stage]['offset'][1]
                    int_x = int(x)
                    int_y = int(y)
                    self.decimal_x = self.decimal_x + x - int_x
                    self.decimal_y = self.decimal_y + y - int_y
                    if self.decimal_x > 0.7:
                        self.decimal_x -= 1
                        int_x += 1
                    if self.decimal_y > 0.7:
                        self.decimal_y -= 1
                        int_y += 1
                    if int_x > 0 or int_y > 0:
                        self.move_r(round(int_x), round(int_y))
                    self.now_num = self.now_num + 1
                if self.now_stage + 1 == len(self.config['games'][self.picked_game][self.picked_gun]) and self.now_num >= self.config['games'][self.picked_game][self.picked_gun][self.now_stage]['number']:
                    self.end = True





    def _update_class_checkboxes(self):
        """更新GUI中的类别多选框"""
        try:
            class_num = self.get_current_class_num()
            class_ary = list(range(class_num))
            self.create_checkboxes(class_ary)
            self.update_class_aim_combo()
            self.update_target_reference_class_combo()
        except Exception as e:
            note_suppressed('_update_class_checkboxes', e)
            return None

    def start(self):
        self.buff_single = Buff_Single()
        # 直接启动，无需验证
        self.verified = True
        self.gui()

    def go(self):
        # 直接启动，无需验证
        self.verified = True
        model_path = self.config['groups'][self.group]['infer_model']
  
        if not os.path.exists(model_path) and (not (self.decrypted_model_data is not None and self.original_model_path == model_path)):
            print('模型文件不存在')
            return False
        self.config['screen_width'] = self.screen_width
        self.config['screen_height'] = self.screen_height
     
        if self.screenshot_manager is None:
            self.screenshot_manager = ScreenshotManager(self.config, self.engine)
        if not self.screenshot_manager.init_sources():
            print('初始化截图源失败')
            return False
        self.init_mouse()
        if self.engine is None:
            print('推理引擎未加载：截图源和输入设备已初始化，推理/扳机线程保持待机')
            return True
        if self.timer_id!= 0:
            self.time_kill_event(self.timer_id)
            self.timer_id = 0
        self.timer_id = self.time_set_event(1, 1, self.aim_bot, 0, 1)
        infer_thread = Thread(target=self.infer)
        infer_thread.setDaemon(True)
        infer_thread.start()
        trigger_thread = Thread(target=self.trigger)
        trigger_thread.setDaemon(True)
        trigger_thread.start()
        return True

    def get_current_aim_center(self):
        cfg = self.config.get('crosshair_color_lock', {})
        if isinstance(cfg, dict) and cfg.get('enabled'):
            dx, dy = self._crosshair_tracker.offset
            return (self.screen_center_x + dx, self.screen_center_y + dy)
        return (self.screen_center_x, self.screen_center_y)

    def _try_crosshair_pull(self, crosshair_cfg):
        """委托给 CrosshairTracker，返回移动量后调用 execute_move"""
        fallback_dz = self.pressed_key_config.get('move_deadzone', 1.0)
        move = self._crosshair_tracker.try_pull(crosshair_cfg, fallback_dz)
        if move is not None:
            self.execute_move(move[0], move[1])

    def aim_bot_func(self, uTimerID, uMsg, dwUser, dw1, dw2):
        crosshair_cfg = self._get_crosshair_lock_config()
        crosshair_enabled = bool(crosshair_cfg.get('enabled'))
        # 逐键准星找色开关：默认 True（兼容旧配置）
        current_key = self.old_pressed_aim_key
        key_use_crosshair = True
        if current_key and current_key in self.aim_keys_dist:
            key_use_crosshair = bool(self.aim_keys_dist[current_key].get('use_crosshair', True))
        crosshair_active = crosshair_enabled and key_use_crosshair
        # 仅瞄准时启用逻辑
        only_when_aiming = bool(crosshair_cfg.get('only_when_aiming', True))
        
        if self.aim_key_status:
            desired_mode = 'aim'
        elif crosshair_active and not only_when_aiming:
            desired_mode = 'crosshair'
        else:
            desired_mode = 'idle'
            
        if desired_mode != self.control_mode:
            if desired_mode == 'aim' or self.control_mode == 'aim':
                self.aim_pid.reset()
                if hasattr(self, 'aim_pipeline') and self.aim_pipeline is not None:
                    self.aim_pipeline.reset()
                try:
                    while not self.que_aim.empty():
                        self.que_aim.get_nowait()
                except Exception:
                    pass
            self.control_mode = desired_mode
            
        if self.aim_key_status:
            try:
                aim_data = self.que_aim.get_nowait()
            except queue.Empty:
                aim_data = None
            if isinstance(aim_data, dict):
                try:
                    aim_bot_scope = float(self.get_dynamic_aim_scope())
                except Exception:
                    aim_bot_scope = 0
                cx, cy = self.get_current_aim_center()
                if hasattr(self, 'engine') and self.engine:
                    model_area = self._cached_model_area
                    if model_area is None:
                        _shape = self.engine.get_input_shape()
                        model_area = _shape[3] * _shape[2]
                        self._cached_model_area = model_area
                else:
                    model_area = 102400
                current_key = self.old_pressed_aim_key
                auto_y = False
                if current_key in self.aim_keys_dist:
                    auto_y = bool(self.aim_keys_dist[current_key].get('auto_y', False))
                move = self.aim_pipeline.step_frame(
                    frame_payload=aim_data,
                    pressed_key_config=self.pressed_key_config,
                    cfg=self.config,
                    center_xy=(cx, cy),
                    aim_scope=aim_bot_scope,
                    identify_left=self.identify_rect_left,
                    identify_top=self.identify_rect_top,
                    model_area=model_area,
                    auto_y=auto_y,
                    left_pressed_long=self.left_pressed_long,
                    debug=self.debug_prediction,
                )
                if move is not None:
                    self.execute_move(move[0], move[1])
                elif crosshair_active and only_when_aiming:
                    self._try_crosshair_pull(crosshair_cfg)
        elif crosshair_active and not only_when_aiming:
            self._try_crosshair_pull(crosshair_cfg)

    def execute_move(self, relative_move_x, relative_move_y):
        if self.config.get('use_async_move', False):
            move_thread = Thread(target=self._execute_move_async, args=(relative_move_x, relative_move_y))
            move_thread.daemon = True
            move_thread.start()
        else:
            self._execute_move_async(relative_move_x, relative_move_y)

    def _emit_move_rel(self, dx, dy):
        ix = int(round(float(dx)))
        iy = int(round(float(dy)))
        if ix == 0 and iy == 0:
            return (0, 0)
        self.move_r(ix, iy)
        return (ix, iy)

    def _execute_move_async(self, relative_move_x, relative_move_y):
        cfg = self.config
        if cfg['is_curve'] or (cfg['is_curve_uniform'] and self.AimController.is_uniform_motion(cfg['show_motion_speed'])):
            skip_zero = cfg['is_curve']  # is_curve 跳过零移动, is_curve_uniform 不跳过
            curve = HumanCurve((0, 0), (round(relative_move_x), round(relative_move_y)), offsetBoundaryX=cfg['offset_boundary_x'], offsetBoundaryY=cfg['offset_boundary_y'], knotsCount=cfg['knots_count'], distortionMean=cfg['distortion_mean'], distortionStdev=cfg['distortion_st_dev'], distortionFrequency=cfg['distortion_frequency'], targetPoints=cfg['target_points'])
            curve = curve.points
            if isinstance(curve, tuple):
                self._emit_move_rel(relative_move_x, relative_move_y)
            else:
                if cfg['is_show_curve']:
                    print(f'曲线点数: {len(curve)}')
                for i in range(1, len(curve)):
                    x = round(curve[i][0] - curve[i - 1][0])
                    y = round(curve[i][1] - curve[i - 1][1])
                    if skip_zero and x == 0 and y == 0:
                        continue
                    self._emit_move_rel(x, y)
        else:
            self._emit_move_rel(relative_move_x, relative_move_y)

    def on_start_button_click(self, sender, app_data):
        current_label = dpg.get_item_label(sender)
        if current_label == '启动':
            # 直接启动，无需验证
            self.verified = True
            dpg.configure_item(sender, label='别点我!!!')
            self.running = True
            if self.config['groups'][self.group].get('is_trt', False) and TENSORRT_AVAILABLE:
                print('检测到TRT模式，开始检查引擎文件...')
                current_model = self.config['groups'][self.group]['infer_model']
                engine_path = os.path.splitext(current_model)[0] + '.engine'
                if not os.path.exists(engine_path):
                    print(f'引擎文件不存在: {engine_path}')
                    print('开始转换TRT引擎...')
                    dpg.set_value('output_text', '正在转换TRT引擎，请稍候...')
                    if current_model.endswith('.ZTX') and self.decrypted_model_data is not None:
                        print('从内存数据转换TRT引擎...')
                        if ensure_engine_from_memory is not None:
                            final_engine_path = ensure_engine_from_memory(self.decrypted_model_data, engine_path, target_hw=None)
                        else:
                            print('TensorRT模块未加载，无法转换引擎')
                            self.config['groups'][self.group]['is_trt'] = False
                            dpg.set_value(self.is_trt_checkbox, False)
                            dpg.set_value('output_text', 'TensorRT模块未加载，使用ONNX模式')
                            return
                        if os.path.exists(final_engine_path):
                            print(f'TRT引擎转换成功: {final_engine_path}')
                            self.config['groups'][self.group]['infer_model'] = final_engine_path
                            dpg.set_value(self.infer_model_input, final_engine_path)
                            dpg.set_value('output_text', 'TRT引擎转换成功')
                        else:
                            print('TRT引擎转换失败，将使用原始模型')
                            self.config['groups'][self.group]['is_trt'] = False
                            dpg.set_value(self.is_trt_checkbox, False)
                            dpg.set_value('output_text', 'TRT引擎转换失败，使用ONNX模式')
                    elif current_model.endswith('.onnx'):
                        print('从ONNX文件转换TRT引擎...')
                        from inference.inference_engine import auto_convert_engine
                        if auto_convert_engine(current_model):
                            print(f'TRT引擎转换成功: {engine_path}')
                            self.config['groups'][self.group]['infer_model'] = engine_path
                            dpg.set_value(self.infer_model_input, engine_path)
                            dpg.set_value('output_text', 'TRT引擎转换成功')
                        else:
                            print('TRT引擎转换失败，将使用原始模型')
                            self.config['groups'][self.group]['is_trt'] = False
                            dpg.set_value(self.is_trt_checkbox, False)
                            dpg.set_value('output_text', 'TRT引擎转换失败，使用ONNX模式')
                else:
                    print(f'找到现有引擎文件: {engine_path}')
                    self.config['groups'][self.group]['infer_model'] = engine_path
                    dpg.set_value(self.infer_model_input, engine_path)
                    dpg.set_value('output_text', 'TRT引擎已就绪')
            model_path = self.config['groups'][self.group]['infer_model']
            if model_path.endswith('.ZTX'):
                self._update_class_checkboxes()
            if self.go():
                dpg.configure_item(sender, label='停止')
            else:
                dpg.configure_item(sender, label='启动')
        else:
            dpg.configure_item(sender, label='别点我!!!')
            self.running = False
            if self.timer_id!= 0:
                self.time_kill_event(self.timer_id)
                self.timer_id = 0
            if self.timer_id2!= 0:
                self.time_kill_event(self.timer_id2)
                self.timer_id2 = 0
            self.close_screenshot()
            self.unmask_all()
            self.stop_listen()
            dpg.configure_item(sender, label='启动')

    def reset_down_status(self):
        if self.config['is_show_down']:
            print(self.now_stage, self.now_num)
        self.now_num = 0
        self.now_stage = 0
        self.decimal_x = 0
        self.decimal_y = 0
        self.end = False

    def close_screenshot(self):
        """关闭并释放截图资源"""
        if self.screenshot_manager is not None:
            self.screenshot_manager.close()
            self.screenshot_manager = None

from inference.inference_engine import TensorRTInferenceEngine, auto_convert_engine

def auto_convert_engine(onnx_path):
    """\n    增强版的自动转换函数，会先检查TensorRT环境是否可用\n    \n    Args:\n        onnx_path: ONNX模型的路径\n        \n    Returns:\n        bool: 转换是否成功\n    """
    if not TENSORRT_AVAILABLE:
        print('TensorRT环境不可用，无法转换为TRT引擎')
        return False
    from inference.inference_engine import auto_convert_engine as original_auto_convert_engine
    return original_auto_convert_engine(onnx_path)

def global_exception_hook(exctype, value, tb):
    with open('error_log.txt', 'a', encoding='utf-8') as f:
        f.write(f"[全局异常] {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(''.join(traceback.format_exception(exctype, value, tb)))
        f.write('\n')
    print('程序发生未捕获异常，详细信息已写入 error_log.txt。请将该文件反馈给开发者。')
sys.excepthook = global_exception_hook
if hasattr(threading, 'excepthook'):
    def thread_exception_hook(args):
        with open('error_log.txt', 'a', encoding='utf-8') as f:
            f.write(f"[线程异常] {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(''.join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)))
            f.write('\n')
        print('子线程发生未捕获异常，详细信息已写入 error_log.txt。请将该文件反馈给开发者。')
    threading.excepthook = thread_exception_hook
if __name__ == '__main__':
    import traceback
    try:
        valorant = Valorant()
        valorant.start()
    except Exception as e:
        with open('error_log.txt', 'w', encoding='utf-8') as f:
            f.write(traceback.format_exc())
        print('程序发生错误，详细信息已写入 error_log.txt。请将该文件反馈给开发者。')
