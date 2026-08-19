# -*- coding: utf-8 -*-
"""推理配置 Mixin - 从 core.py 抽取的推理引擎/模型配置相关 UI 回调与辅助方法。

两段非连续区块（被 reset_down_status/close_screenshot 跨切面方法隔断）:
  1. on_is_v8/auto_y/use_crosshair/right_down_change + init_target_priority
  2. on_is_show_priority_debug/is_trt/show_infer_time/show_fov_change +
     get_trt/onnx/current_class_num + on_gui_dpi_scale_change + on_reset_dpi_scale_click
所有方法通过 self.* 访问 Valorant 实例;通过 mix-in 继承可用。
"""
import os
import dearpygui.dearpygui as dpg
from threading import Timer
from ..runtime import TENSORRT_AVAILABLE


class InferConfigMixin:
    """推理引擎/模型配置回调与类别数查询 Mixin。

    依赖 Valorant 提供:
      self.config / self.group / self.decrypted_model_data
      self.refresh_engine() (InferenceMixin) / self.create_checkboxes() (core)
      self.update_class_aim_combo() / self.update_target_reference_class_combo() (core)
      self.get_system_dpi_scale() (core) / self.is_trt_checkbox / self.dpi_scale_slider
      TENSORRT_AVAILABLE (from core 延迟导入)
    """

    def on_is_v8_change(self, sender, app_data):
        self.config['groups'][self.group]['is_v8'] = app_data
        print(f"changed to: {self.config['groups'][self.group]['is_v8']}")

    def on_auto_y_change(self, sender, app_data):
        if len(self.aim_key) > 0:
            self.config['groups'][self.group]['aim_keys'][self.select_key]['auto_y'] = app_data
            print(f'按键 {self.select_key} 长按左键不锁Y轴设置已更改为: {app_data}')

    def on_use_crosshair_change(self, sender, app_data):
        if len(self.aim_key) > 0:
            self.config['groups'][self.group]['aim_keys'][self.select_key]['use_crosshair'] = app_data
            print(f'按键 {self.select_key} 准星找色已更改为: {app_data}')

    def on_right_down_change(self, sender, app_data):
        self.config['groups'][self.group]['right_down'] = app_data
        print(f"changed to: {self.config['groups'][self.group]['right_down']}")

    def init_target_priority(self):
        self.target_priority = {'distance_scoring_weight': self.config['distance_scoring_weight'], 'center_scoring_weight': self.config['center_scoring_weight'], 'size_scoring_weight': self.config['size_scoring_weight']}
    def on_is_show_priority_debug_change(self, sender, app_data):
        self.config['is_show_priority_debug'] = app_data
        print(f'类别优先级调试: {app_data}')

    def on_is_trt_change(self, sender, app_data):
        self.config['groups'][self.group]['is_trt'] = app_data
        if app_data:
            if not TENSORRT_AVAILABLE:
                print('TensorRT环境未安装或不可用')
                print('请安装以下组件：')
                print('1. CUDA Toolkit')
                print('2. cuDNN')
                print('3. TensorRT')
                print('4. 具体配置教程查看:https://www.yuque.com/huiyestudio/dqrld3/rislyof9zegdfira')
                self.config['groups'][self.group]['is_trt'] = False
                dpg.set_value(self.is_trt_checkbox, False)
                dpg.add_text('TensorRT环境未安装，已自动切换为ONNX推理模式', color=[255, 100, 100], tag='trt_error_message')

                def remove_message():
                    if dpg.does_item_exist('trt_error_message'):
                        dpg.delete_item('trt_error_message')
                Timer(5.0, remove_message).start()
                return
            current_model = self.config['groups'][self.group]['infer_model']
            if current_model.endswith('.ZTX') and self.decrypted_model_data is not None:
                self.config['groups'][self.group]['original_infer_model'] = current_model
                print('已启用TRT模式，将在启动时检测并转换引擎文件')
            elif current_model.endswith('.onnx'):
                self.config['groups'][self.group]['original_infer_model'] = current_model
                print('已启用TRT模式，将在启动时检测并转换引擎文件')
            elif current_model.endswith('.engine'):
                onnx_path = self.config['groups'][self.group].get('original_infer_model', None)
                if not onnx_path:
                    possible_onnx = os.path.splitext(current_model)[0] + '.onnx'
                    if os.path.exists(possible_onnx):
                        self.config['groups'][self.group]['original_infer_model'] = possible_onnx
                        print(f'已自动推断并设置原始模型路径: {possible_onnx}')
                    else:
                        print('警告: 无法找到对应的ONNX模型，TRT切换可能不正常')
            else:
                print('当前模型不是onnx、ZTX或engine格式，无法正确处理TRT模式。')
                self.config['groups'][self.group]['is_trt'] = False
                dpg.set_value(self.is_trt_checkbox, False)
        else:
            current_model = self.config['groups'][self.group]['infer_model']
            if current_model.endswith('.engine'):
                dopa_path = self.config['groups'][self.group].get('original_infer_model', None)
                if dopa_path and dopa_path.endswith('.ZTX') and (self.decrypted_model_data is not None):
                    self.config['groups'][self.group]['infer_model'] = dopa_path
                    self.refresh_engine()
                    dpg.set_value(self.infer_model_input, dopa_path)
                    is_v8 = self.config['groups'][self.group].get('is_v8', False)
                    dpg.set_value(self.is_v8_checkbox, is_v8)
                    print(f'V8自动勾选状态: {is_v8}')
                    return
            elif current_model.endswith('.ZTX') and self.decrypted_model_data is not None:
                self.refresh_engine()
                is_v8 = self.config['groups'][self.group].get('is_v8', False)
                dpg.set_value(self.is_v8_checkbox, is_v8)
                print(f'V8自动勾选状态: {is_v8}')
                return
            onnx_path = self.config['groups'][self.group].get('original_infer_model', None)
            if onnx_path and os.path.exists(onnx_path):
                self.config['groups'][self.group]['infer_model'] = onnx_path
                self.refresh_engine()
                dpg.set_value(self.infer_model_input, onnx_path)
                is_v8 = self.config['groups'][self.group].get('is_v8', False)
                dpg.set_value(self.is_v8_checkbox, is_v8)
                print(f'已切换回 ONNX Runtime 推理，V8自动勾选状态: {is_v8}')
            else:
                print('未找到原始ONNX模型路径，请检查配置。')
        class_num = self.get_current_class_num()
        class_ary = list(range(class_num))
        self.create_checkboxes(class_ary)
        self.update_class_aim_combo()
        self.update_target_reference_class_combo()

    def on_show_infer_time_change(self, sender, app_data):
        self.config['show_infer_time'] = app_data
        print(f'显示推理时间: {app_data}')

    def on_show_fov_change(self, sender, app_data):
        self.config['show_fov'] = app_data
        print(f'显示瞄准范围: {app_data}')


    def get_trt_class_num(self):
        if not TENSORRT_AVAILABLE:
            print('TensorRT环境不可用，尝试从ONNX推断类别数')
            return self.get_onnx_class_num()
        if not hasattr(self.engine, 'engine'):
            print('当前推理引擎不是 TensorRTInferenceEngine，无法获取类别数。')
            return self.get_onnx_class_num()
        try:
            binding = self.engine.engine[1]
            shape = self.engine.engine.get_tensor_shape(binding)
        except Exception as e:
            return self.get_onnx_class_num()
        if len(shape) == 3 and shape[0] == 1 and (shape[1] == 5):
            trt_class_num = self.config['groups'][self.group].get('trt_class_num', None)
            if trt_class_num is not None:
                print(f'使用config中预设的TRT类别数: {trt_class_num}')
                return trt_class_num
            return self.get_onnx_class_num()
        c = shape[(-1)]
        if 1 <= c - 4 <= 200:
            return c - 4
        if 1 <= c - 5 <= 200:
            return c - 5
        if len(shape) == 2 and 1 <= shape[1] <= 200:
            return shape[1]
        else:
            return self.get_onnx_class_num()

    def get_onnx_class_num(self):
        """从ONNX模型推断类别数"""
        onnx_path = self.config['groups'][self.group].get('original_infer_model', '')
        if not onnx_path:
            current_model = self.config['groups'][self.group]['infer_model']
            if current_model.endswith('.engine'):
                onnx_path = os.path.splitext(current_model)[0] + '.onnx'
            else:
                onnx_path = current_model
        try:
            import onnxruntime as ort
            session = None
            if onnx_path.endswith('.ZTX') and self.decrypted_model_data is not None:
                providers = ['DmlExecutionProvider', 'CPUExecutionProvider'] if 'DmlExecutionProvider' in ort.get_available_providers() else ['CPUExecutionProvider']
                session = ort.InferenceSession(self.decrypted_model_data, providers=providers)
            elif onnx_path and os.path.exists(onnx_path) and (not onnx_path.endswith('.ZTX')):
                providers = ['DmlExecutionProvider', 'CPUExecutionProvider'] if 'DmlExecutionProvider' in ort.get_available_providers() else ['CPUExecutionProvider']
                session = ort.InferenceSession(onnx_path, providers=providers)
            if session is not None:
                outputs = session.get_outputs()
                if len(outputs) > 0:
                    onnx_shape = outputs[0].shape
                    if len(onnx_shape) >= 2:
                        if onnx_shape[(-2)] > 4:
                            class_num = onnx_shape[(-2)] - 4
                            return class_num
                        if onnx_shape[(-1)] > 5:
                            class_num = onnx_shape[(-1)] - 5
                            return class_num
                del session
                return 5
            return 5
        except Exception as e:
            print(f'从ONNX推断类别数失败: {e}')
            return 5

    def get_current_class_num(self):
        try:
            if self.engine is None:
                return 5
            if self.config['groups'][self.group]['infer_model'].endswith('.engine'):
                if not TENSORRT_AVAILABLE:
                    result = self.get_onnx_class_num()
                    return result
                result = self.get_trt_class_num()
                return result
            if self.config['groups'][self.group]['is_v8']:
                result = self.engine.get_class_num_v8()
                if isinstance(result, (int, float)) and result > 0:
                    return int(result)
                return 5
            result = self.engine.get_class_num()
            if isinstance(result, (int, float)) and result > 0:
                return int(result)
            return 5
        except Exception as e:
            import traceback
            print(f'获取类别数异常: {e}')
            traceback.print_exc()
            return 1

    def on_gui_dpi_scale_change(self, sender, app_data):
        """DPI缩放变化回调"""
        self.config['gui_dpi_scale'] = app_data
        print(f'DPI缩放已更改为: {app_data:.2f}, 重启应用后生效')

    def on_reset_dpi_scale_click(self, sender, app_data):
        """重置DPI缩放到自动检测值"""
        auto_scale = self.get_system_dpi_scale()
        self.config['gui_dpi_scale'] = 0.0
        dpg.set_value(self.dpi_scale_slider, auto_scale)
        print(f'DPI缩放已重置为自动检测: {auto_scale:.2f}, 重启应用后生效')
