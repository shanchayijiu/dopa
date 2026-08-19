# -*- coding: utf-8 -*-
"""瞄准配置 Mixin - 从 core.py 抽取的瞄准/精度参数配置回调与辅助方法。

包括：on_group_change/confidence_threshold/iou_t/infer_model/select_model_click/
aim_bot_position(2)/target_sticky/large_target_threshold/boost/class_priority/
class_aim_combo/aim_bot_scope/dynamic_scope*/min_position/smoothing_factor/
base_step/distance_weight/fov_angle/history_size/deadzone/smoothing/
velocity_decay/current/last_frame_weight/output_scale/uniform_threshold/
min/max_velocity/compensation_factor/overshoot_*。
另含 parse/format/get_class_priority、update_class_aim_inputs/combo 等辅助方法。
"""
import os

import dearpygui.dearpygui as dpg

from inference.v11onnx_support import infer_model_variant_from_path


class AimConfigMixin:
    """瞄准与精度参数配置回调 Mixin。

    依赖 Valorant 提供:
      self.config / self.group / self.select_key / self.aim_keys_dist / self.aim_key
      self.refresh_controller_params() (core) / self.create_checkboxes() (core)
      self.update_class_aim_combo / self.update_target_reference_class_combo (core)
      self.update_rect() (TriggerMixin) / self.update_class_aim_inputs (本域)
      self.is_trt_checkbox / self.infer_model_input / self.is_v8_checkbox / self.is_aim_v8
    """

    def on_group_change(self, sender, app_data):
        self.select_key = ''
        self.config['group'] = app_data
        self.group = app_data
        if self.verified:
            model_path = self.config['groups'][self.group]['infer_model']
            if model_path.endswith('.ZTX'):
                card = dpg.get_value('card')
                if card is not None and str(card).strip():
                    self._decrypt_encrypted_model(str(card).strip())
        self.refresh_engine()
        class_num = self.get_current_class_num()
        class_ary = list(range(class_num))
        self.create_checkboxes(class_ary)
        self.update_class_aim_combo()
        self.update_target_reference_class_combo()
        self.aim_keys_dist = self.config['groups'][app_data]['aim_keys']
        self.aim_key = list(self.aim_keys_dist.keys())
        self.render_key_combo()
        self.update_group_inputs()
        self.update_auto_flashbang_ui_state()
        print(f"changed to: {self.config['group']}")

    def on_confidence_threshold_change(self, sender, app_data):
        if 'class_aim_positions' not in self.config['groups'][self.group]['aim_keys'][self.select_key]:
            self.config['groups'][self.group]['aim_keys'][self.select_key]['class_aim_positions'] = {}
        if self.current_selected_class not in self.config['groups'][self.group]['aim_keys'][self.select_key]['class_aim_positions']:
            self.config['groups'][self.group]['aim_keys'][self.select_key]['class_aim_positions'][self.current_selected_class] = {'aim_bot_position': 0.0, 'aim_bot_position2': 0.0, 'confidence_threshold': 0.5, 'iou_t': 1.0}
        self.config['groups'][self.group]['aim_keys'][self.select_key]['class_aim_positions'][self.current_selected_class]['confidence_threshold'] = round(app_data, 4)
        print(f'类别 {self.current_selected_class} 置信阈值changed to: {round(app_data, 4)}')

    def on_iou_t_change(self, sender, app_data):
        if 'class_aim_positions' not in self.config['groups'][self.group]['aim_keys'][self.select_key]:
            self.config['groups'][self.group]['aim_keys'][self.select_key]['class_aim_positions'] = {}
        if self.current_selected_class not in self.config['groups'][self.group]['aim_keys'][self.select_key]['class_aim_positions']:
            self.config['groups'][self.group]['aim_keys'][self.select_key]['class_aim_positions'][self.current_selected_class] = {'aim_bot_position': 0.0, 'aim_bot_position2': 0.0, 'confidence_threshold': 0.5, 'iou_t': 1.0}
        self.config['groups'][self.group]['aim_keys'][self.select_key]['class_aim_positions'][self.current_selected_class]['iou_t'] = round(app_data, 4)
        print(f'类别 {self.current_selected_class} IOU阈值changed to: {round(app_data, 4)}')

    def on_infer_model_change(self, sender, app_data):
        self._dopa_warning_shown = False
        if app_data!= '' and os.path.exists(app_data):
            if app_data.endswith('.onnx'):
                self.config['groups'][self.group]['original_infer_model'] = app_data
            elif app_data.endswith('.ZTX') or app_data.endswith('.ZTX'):
                self.config['groups'][self.group]['original_infer_model'] = app_data
            elif app_data.endswith('.engine'):
                onnx_path = os.path.splitext(app_data)[0] + '.onnx'
                if os.path.exists(onnx_path):
                    self.config['groups'][self.group]['original_infer_model'] = onnx_path
                else:
                    print(f'警告：找不到对应的ONNX模型：{onnx_path}，TRT模式切换可能不正常')
            self.config['groups'][self.group]['infer_model'] = app_data
            inferred_variant = infer_model_variant_from_path(
                app_data, bool(self.config['groups'][self.group].get('is_v8', False))
            )
            self.config['groups'][self.group]['model_variant'] = inferred_variant
            if inferred_variant == 'v11onnx':
                # v11onnx 与现有 v8 后处理接口保持一致
                self.config['groups'][self.group]['is_v8'] = True
                print('[v11onnx] 已切换到 v11onnx 模型，自动对齐 v8 后处理路径')
            if (app_data.endswith('.ZTX') or app_data.endswith('.ZTX')) and self.verified:
                card = dpg.get_value('card')
                if card is not None and str(card).strip():
                    self._decrypt_encrypted_model(str(card).strip())
                elif False:pass
            self.refresh_engine()
            class_num = self.get_current_class_num()
            class_ary = list(range(class_num))
            self.create_checkboxes(class_ary)
            self.update_class_aim_combo()
            self.update_target_reference_class_combo()
            self.update_auto_flashbang_ui_state()
            print(app_data + '模型文件存在，已更新')
        else:
            print(app_data + '模型文件不存在，请检查路径是否正确')

    def on_select_model_click(self, sender, app_data):
        """选择模型文件的回调函数"""
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            filetypes = [('所有支持的模型', '*.onnx;*.engine;*.model;*.ztx'), ('ONNX模型', '*.onnx'), ('TensorRT引擎', '*.engine'), ('奶龙加密模型', '*.model'), ('ZTX加密模型', '*.ztx'), ('所有文件', '*.*')]
            file_path = filedialog.askopenfilename(title='选择模型文件', filetypes=filetypes, parent=root)
            root.destroy()
            if file_path:
                valid_extensions = ['.onnx', '.engine', '.ztx']
                file_ext = os.path.splitext(file_path)[1].lower()
                if file_ext in valid_extensions:
                    if hasattr(self, 'is_trt_checkbox') and self.is_trt_checkbox is not None:
                        is_engine = (file_ext == '.engine')
                        dpg.set_value(self.is_trt_checkbox, is_engine)
                        self.config['groups'][self.group]['is_trt'] = is_engine
                    dpg.set_value(self.infer_model_input, file_path)
                    self.on_infer_model_change(self.infer_model_input, file_path)
                else:
                    print(f'不支持的文件格式: {file_ext}')
                    print('支持的格式: .onnx, .engine, .ztx')
        except Exception as e:
            print(f'选择模型文件时出错: {e}')

    def on_aim_bot_position_change(self, sender, app_data):
        if 'class_aim_positions' not in self.config['groups'][self.group]['aim_keys'][self.select_key]:
            self.config['groups'][self.group]['aim_keys'][self.select_key]['class_aim_positions'] = {}
        if self.current_selected_class not in self.config['groups'][self.group]['aim_keys'][self.select_key]['class_aim_positions']:
            self.config['groups'][self.group]['aim_keys'][self.select_key]['class_aim_positions'][self.current_selected_class] = {'aim_bot_position': 0.0, 'aim_bot_position2': 0.0}
        self.config['groups'][self.group]['aim_keys'][self.select_key]['class_aim_positions'][self.current_selected_class]['aim_bot_position'] = round(app_data, 4)
        print(f'类别 {self.current_selected_class} 瞄准部位1 changed to: {round(app_data, 4)}')

    def on_aim_bot_position2_change(self, sender, app_data):
        if 'class_aim_positions' not in self.config['groups'][self.group]['aim_keys'][self.select_key]:
            self.config['groups'][self.group]['aim_keys'][self.select_key]['class_aim_positions'] = {}
        if self.current_selected_class not in self.config['groups'][self.group]['aim_keys'][self.select_key]['class_aim_positions']:
            self.config['groups'][self.group]['aim_keys'][self.select_key]['class_aim_positions'][self.current_selected_class] = {'aim_bot_position': 0.0, 'aim_bot_position2': 0.0}
        self.config['groups'][self.group]['aim_keys'][self.select_key]['class_aim_positions'][self.current_selected_class]['aim_bot_position2'] = round(app_data, 4)
        print(f'类别 {self.current_selected_class} 瞄准部位2 changed to: {round(app_data, 4)}')

    def on_target_sticky_pixels_change(self, sender, app_data):
        try:
            v = float(app_data)
        except Exception:
            v = float(self.config.get('target_sticky_pixels', 40.0))
        v = max(0.0, min(120.0, v))
        self.config['target_sticky_pixels'] = round(v, 2)
        print(f'目标黏性像素已设置为: {round(v, 2)}')

    def on_target_lock_ms_change(self, sender, app_data):
        try:
            v = float(app_data)
        except Exception:
            v = float(self.config.get('target_lock_ms', 150.0))
        v = max(0.0, min(500.0, v))
        self.config['target_lock_ms'] = round(v, 0)
        print(f'目标锁定时间已设置为: {round(v, 0)}ms')

    def on_large_target_threshold_change(self, sender, app_data):
        try:
            v = float(app_data)
        except Exception:
            v = float(self.config.get('large_target_threshold', 0.055))
        v = max(0.0, min(0.3, v))
        self.config['large_target_threshold'] = round(v, 4)
        print(f'大目标阈值已设置为: {round(v, 4)}')

    def on_large_target_boost_change(self, sender, app_data):
        try:
            v = float(app_data)
        except Exception:
            v = float(self.config.get('large_target_boost', 1.12))
        v = max(1.0, min(2.5, v))
        self.config['large_target_boost'] = round(v, 3)
        print(f'大目标加权已设置为: {round(v, 3)}')

    def on_class_priority_change(self, sender, app_data):
        """类别优先级输入框回调函数"""
        priority_text = app_data.strip()
        print(f'类别优先级输入: {priority_text}')
        priority_order = self.parse_class_priority(priority_text)
        if priority_order is not None:
            self.config['groups'][self.group]['aim_keys'][self.select_key]['class_priority_order'] = priority_order
            print(f'类别优先级已更新: {priority_order}')
        else:
            print(f'类别优先级格式错误: {priority_text}')

    def parse_class_priority(self, priority_text):
        """解析类别优先级字符串"""
        if not priority_text:
            return []
        try:
            import re
            parts = re.split('[-,\\s]+', priority_text.strip())
            priority_order = []
            seen = set()
            for part in parts:
                if part.strip():
                    try:
                        class_id = int(part.strip())
                        if class_id not in seen:
                            priority_order.append(class_id)
                            seen.add(class_id)
                    except ValueError:
                        return
            else:
                return priority_order
        except Exception:
            return None

    def format_class_priority(self, priority_order):
        """将优先级列表格式化为字符串"""
        return '-'.join(map(str, priority_order)) if priority_order else ''

    def get_class_priority_order(self):
        """获取当前按键的类别优先级顺序"""
        try:
            key_config = self.config['groups'][self.group]['aim_keys'][self.select_key]
            return key_config.get('class_priority_order', [])
        except (KeyError, TypeError):
            return []

    def on_class_aim_combo_change(self, sender, app_data):
        """类别选择下拉框回调函数"""
        if app_data:
            self.current_selected_class = app_data.replace('类别', '')
            print(f'当前选择类别: {self.current_selected_class}')
            self.update_class_aim_inputs()

    def update_class_aim_inputs(self):
        """根据当前选择的类别更新瞄准部位滑动条的值"""
        if not hasattr(self, 'aim_bot_position_slider') or self.aim_bot_position_slider is None:
            return None
        key_cfg = self.config['groups'][self.group]['aim_keys'][self.select_key]
        cap = key_cfg.get('class_aim_positions', {})
        if isinstance(cap, list):
            converted = {}
            for i, item in enumerate(cap):
                if isinstance(item, dict):
                    converted[str(i)] = {'aim_bot_position': float(item.get('aim_bot_position', 0.0)), 'aim_bot_position2': float(item.get('aim_bot_position2', 0.0)), 'confidence_threshold': float(item.get('confidence_threshold', 0.5)), 'iou_t': float(item.get('iou_t', 1.0))}
                else:
                    converted[str(i)] = {'aim_bot_position': 0.0, 'aim_bot_position2': 0.0, 'confidence_threshold': 0.5, 'iou_t': 1.0}
            key_cfg['class_aim_positions'] = converted
        elif not isinstance(cap, dict):
            key_cfg['class_aim_positions'] = {}
        if not self.current_selected_class or not str(self.current_selected_class).isdigit():
            self.current_selected_class = '0'
        if self.current_selected_class not in key_cfg['class_aim_positions']:
            key_cfg['class_aim_positions'][self.current_selected_class] = {'aim_bot_position': 0.0, 'aim_bot_position2': 0.0, 'confidence_threshold': 0.5, 'iou_t': 1.0}
        class_config = key_cfg['class_aim_positions'][self.current_selected_class]
        import dearpygui.dearpygui as dpg
        dpg.set_value(self.aim_bot_position_slider, float(class_config.get('aim_bot_position', 0.0)))
        dpg.set_value(self.aim_bot_position2_slider, float(class_config.get('aim_bot_position2', 0.0)))
        if hasattr(self, 'confidence_threshold_slider') and self.confidence_threshold_slider is not None:
            dpg.set_value(self.confidence_threshold_slider, float(class_config.get('confidence_threshold', 0.5)))
        if hasattr(self, 'iou_t_slider') and self.iou_t_slider is not None:
            dpg.set_value(self.iou_t_slider, float(class_config.get('iou_t', 1.0)))

    def update_class_aim_combo(self):
        """更新类别下拉框的选项"""
        if not hasattr(self, 'class_aim_combo') or self.class_aim_combo is None:
            return None
        try:
            class_num = self.get_current_class_num()
            class_num = int(class_num)
            class_items = [f'类别{i}' for i in range(class_num)]
            import dearpygui.dearpygui as dpg
            dpg.configure_item(self.class_aim_combo, items=class_items)
            if class_items:
                try:
                    current_class_int = int(self.current_selected_class) if self.current_selected_class and self.current_selected_class.isdigit() else (-1)
                    if not self.current_selected_class or current_class_int < 0 or current_class_int >= class_num:
                        self.current_selected_class = '0'
                except (ValueError, TypeError):
                    self.current_selected_class = '0'
                dpg.set_value(self.class_aim_combo, f'类别{self.current_selected_class}')
                self.update_class_aim_inputs()
        except Exception as e:
            import traceback
            traceback.print_exc()

    def on_aim_bot_scope_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['aim_bot_scope'] = app_data
        print(f"changed to: {self.config['groups'][self.group]['aim_keys'][self.select_key]['aim_bot_scope']}")

    def on_dynamic_scope_enabled_change(self, sender, app_data):
        key_cfg = self.config['groups'][self.group]['aim_keys'][self.select_key]
        if 'dynamic_scope' not in key_cfg:
            key_cfg['dynamic_scope'] = {}
        key_cfg['dynamic_scope']['enabled'] = bool(app_data)

    def on_dynamic_scope_min_ratio_change(self, sender, app_data):
        key_cfg = self.config['groups'][self.group]['aim_keys'][self.select_key]
        if 'dynamic_scope' not in key_cfg:
            key_cfg['dynamic_scope'] = {}
        try:
            v = float(app_data)
        except Exception:
            v = 0.5
        v = max(0.0, min(1.0, v))
        key_cfg['dynamic_scope']['min_ratio'] = v

    def on_dynamic_scope_min_scope_change(self, sender, app_data):
        key_cfg = self.config['groups'][self.group]['aim_keys'][self.select_key]
        if 'dynamic_scope' not in key_cfg:
            key_cfg['dynamic_scope'] = {}
        try:
            v = int(app_data)
        except Exception:
            v = 0
        key_cfg['dynamic_scope']['min_scope'] = max(0, v)

    def on_dynamic_scope_shrink_ms_change(self, sender, app_data):
        key_cfg = self.config['groups'][self.group]['aim_keys'][self.select_key]
        if 'dynamic_scope' not in key_cfg:
            key_cfg['dynamic_scope'] = {}
        try:
            v = int(app_data)
        except Exception:
            v = 300
        key_cfg['dynamic_scope']['shrink_duration_ms'] = max(0, v)

    def on_dynamic_scope_recover_ms_change(self, sender, app_data):
        key_cfg = self.config['groups'][self.group]['aim_keys'][self.select_key]
        if 'dynamic_scope' not in key_cfg:
            key_cfg['dynamic_scope'] = {}
        try:
            v = int(app_data)
        except Exception:
            v = 300
        key_cfg['dynamic_scope']['recover_duration_ms'] = max(0, v)

    def on_min_position_offset_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['min_position_offset'] = app_data
        print(f"changed to: {self.config['groups'][self.group]['aim_keys'][self.select_key]['min_position_offset']}")

    def on_smoothing_factor_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['smoothing_factor'] = round(app_data, 3)
        self.refresh_controller_params()
        print(f"changed to: {self.config['groups'][self.group]['aim_keys'][self.select_key]['smoothing_factor']}")

    def on_base_step_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['base_step'] = round(app_data, 3)
        self.refresh_controller_params()
        print(f"changed to: {self.config['groups'][self.group]['aim_keys'][self.select_key]['base_step']}")

    def on_distance_weight_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['distance_weight'] = round(app_data, 3)
        self.refresh_controller_params()
        print(f"changed to: {self.config['groups'][self.group]['aim_keys'][self.select_key]['distance_weight']}")

    def on_fov_angle_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['fov_angle'] = round(app_data, 3)
        self.refresh_controller_params()
        print(f"changed to: {self.config['groups'][self.group]['aim_keys'][self.select_key]['fov_angle']}")

    def on_history_size_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['history_size'] = round(app_data, 3)
        self.refresh_controller_params()
        print(f"changed to: {self.config['groups'][self.group]['aim_keys'][self.select_key]['history_size']}")

    def on_deadzone_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['deadzone'] = round(app_data, 3)
        self.refresh_controller_params()
        print(f"changed to: {self.config['groups'][self.group]['aim_keys'][self.select_key]['deadzone']}")

    def on_smoothing_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['smoothing'] = round(app_data, 3)
        self.refresh_controller_params()
        print(f"changed to: {self.config['groups'][self.group]['aim_keys'][self.select_key]['smoothing']}")

    def on_velocity_decay_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['velocity_decay'] = round(app_data, 3)
        self.refresh_controller_params()
        print(f"changed to: {self.config['groups'][self.group]['aim_keys'][self.select_key]['velocity_decay']}")

    def on_current_frame_weight_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['current_frame_weight'] = round(app_data, 3)
        self.refresh_controller_params()
        print(f"changed to: {self.config['groups'][self.group]['aim_keys'][self.select_key]['current_frame_weight']}")

    def on_last_frame_weight_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['last_frame_weight'] = round(app_data, 3)
        self.refresh_controller_params()
        print(f"changed to: {self.config['groups'][self.group]['aim_keys'][self.select_key]['last_frame_weight']}")

    def on_output_scale_x_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['output_scale_x'] = round(app_data, 3)
        self.refresh_controller_params()
        print(f"changed to: {self.config['groups'][self.group]['aim_keys'][self.select_key]['output_scale_x']}")

    def on_output_scale_y_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['output_scale_y'] = round(app_data, 3)
        self.refresh_controller_params()
        print(f"changed to: {self.config['groups'][self.group]['aim_keys'][self.select_key]['output_scale_y']}")

    def on_uniform_threshold_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['uniform_threshold'] = round(app_data, 3)
        self.refresh_controller_params()
        print(f"changed to: {self.config['groups'][self.group]['aim_keys'][self.select_key]['uniform_threshold']}")

    def on_min_velocity_threshold_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['min_velocity_threshold'] = round(app_data, 3)
        self.refresh_controller_params()
        print(f"changed to: {self.config['groups'][self.group]['aim_keys'][self.select_key]['min_velocity_threshold']}")

    def on_max_velocity_threshold_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['max_velocity_threshold'] = round(app_data, 3)
        self.refresh_controller_params()
        print(f"changed to: {self.config['groups'][self.group]['aim_keys'][self.select_key]['max_velocity_threshold']}")

    def on_compensation_factor_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['compensation_factor'] = round(app_data, 3)
        self.refresh_controller_params()
        print(f"changed to: {self.config['groups'][self.group]['aim_keys'][self.select_key]['compensation_factor']}")

    def on_overshoot_threshold_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['overshoot_threshold'] = round(app_data, 1)
        self.refresh_controller_params()
        print(f"过冲检测阈值: {self.config['groups'][self.group]['aim_keys'][self.select_key]['overshoot_threshold']}")

    def on_overshoot_x_factor_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['overshoot_x_factor'] = round(app_data, 2)
        self.refresh_controller_params()
        print(f"X轴过冲抑制系数: {self.config['groups'][self.group]['aim_keys'][self.select_key]['overshoot_x_factor']}")

    def on_overshoot_y_factor_change(self, sender, app_data):
        self.config['groups'][self.group]['aim_keys'][self.select_key]['overshoot_y_factor'] = round(app_data, 2)
        self.refresh_controller_params()
        print(f"Y轴过冲抑制系数: {self.config['groups'][self.group]['aim_keys'][self.select_key]['overshoot_y_factor']}")
