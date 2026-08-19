# -*- coding: utf-8 -*-
"""授权校验与模型解密 Mixin - 从 core.py 抽取的验证/解密/安全清理方法。

包括：start_verify_init/error_exit/verify/_decrypt_encrypted_model/
_validate_onnx_data/_secure_cleanup/is_using_dopa_model/is_using_encrypted_model。

TENSORRT_AVAILABLE 在调用时从 core_runtime 读取，不做导入期快照：
core_runtime 在引擎导入失败时会把该标志降级为 False。
"""
import dearpygui.dearpygui as dpg

from inference.decode_model import build_model
from util.diagnostics import note_suppressed


def _tensorrt_available():
    """调用时读取 core_runtime.TENSORRT_AVAILABLE，不做导入期快照。"""
    from .. import runtime as core_runtime

    return getattr(core_runtime, "TENSORRT_AVAILABLE", False)


class VerifyMixin:
    """授权校验、加密模型解密与敏感数据清理 Mixin。

    依赖 Valorant 提供:
      self.config / self.group / self.verified / self.running / self.versionID
      self.decrypted_model_data / self.original_model_path / self.screenshot_manager
      self.engine / self.timer_id2 / self.time_kill_event()
      self.refresh_engine() (InferenceMixin) / self._update_class_checkboxes() (core)
    """

    def start_verify_init(self):
        # 本地验证模式 - 无需网络
        self.versionID = '1.0'
        self.verified = True
        print('[verify]本地验证模式: 初始化成功')

    def error_exit(self, extra_message=None):
        try:
            self.verified = False
            self.running = False
        except Exception:
            pass
        try:
            if getattr(self, 'timer_id2', 0)!= 0:
                self.time_kill_event(self.timer_id2)
                self.timer_id2 = 0
        except Exception:
            pass
        try:
            if getattr(self, 'screenshot_manager', None) is not None:
                stop_method = getattr(self.screenshot_manager, 'stop', None)
                if callable(stop_method):
                    stop_method()
        except Exception:
            pass
        try:
            if getattr(self, 'engine', None) is not None:
                close_method = getattr(self.engine, 'close', None)
                if callable(close_method):
                    close_method()
        except Exception:
            pass
        try:
            msg = '验证过程中出现错误'
            if extra_message:
                msg = f'{msg}：{extra_message}'
            if dpg.does_item_exist('output_text'):
                dpg.set_value('output_text', msg)
        except Exception:
            return None

    def verify(self):
        # 直接返回成功，无需验证
        self.verified = True
        dpg.set_value('output_text', '程序已启动')
        # 使用默认模型路径
        model_path = self.config['groups'][self.group]['infer_model']
        if model_path.endswith(('.onnx', '.engine', '.ZTX')):
            self._decrypt_encrypted_model('local_user')

    def _decrypt_encrypted_model(self, username):
        """检查并解密文件（支持ZTX和ZTX格式）"""
        try:
            model_path = self.config['groups'][self.group]['infer_model']
            if model_path.endswith('.ZTX') or model_path.endswith('.ZTX'):
                decrypted_data = build_model(model_path, username)
                if decrypted_data is not None:
                    if self._validate_onnx_data(decrypted_data):
                        self.decrypted_model_data = decrypted_data
                        self.original_model_path = model_path
                        self.refresh_engine()
                        self._update_class_checkboxes()
                    else:
                        self._secure_cleanup()
                else:
                    self._secure_cleanup()
            else:
                self._secure_cleanup()
                if model_path.endswith(('.onnx', '.engine')):
                    self.refresh_engine()
                    self._update_class_checkboxes()
        except Exception as e:
            note_suppressed('_decrypt_encrypted_model', e)
            self._secure_cleanup()

    def _validate_onnx_data(self, data):
        """验证数据是否为有效的ONNX格式"""
        try:
            import onnxruntime as rt
            providers = ['DmlExecutionProvider', 'CPUExecutionProvider'] if 'DmlExecutionProvider' in rt.get_available_providers() else ['CPUExecutionProvider']
            temp_session = rt.InferenceSession(data, providers=providers)
            del temp_session
            return True
        except Exception as e:
            return False

    def _secure_cleanup(self):
        # 安全清理敏感数据
        try:
            try:
                if self.decrypted_model_data is not None:
                    self.decrypted_model_data = b'\x00' * len(self.decrypted_model_data)
                    self.decrypted_model_data = None
                if hasattr(self, 'screenshot_manager') and self.screenshot_manager is not None:
                    try:
                        self.screenshot_manager.close()
                    except Exception as e:
                        note_suppressed('_secure_cleanup/screenshot_manager.close', e)
                self.original_model_path = None
                try:
                    if _tensorrt_available():
                        try:
                            import pycuda.driver as cuda
                        except ImportError:
                            from inference import cuda_compat as cuda
                        try:
                            current_ctx = cuda.Context.get_current()
                            if current_ctx is not None:
                                current_ctx.pop()
                        except cuda.LogicError:
                            pass
                except Exception as e:
                    note_suppressed('_secure_cleanup/cuda-ctx', e)
            except Exception as e:
                note_suppressed('_secure_cleanup/inner', e)
        except Exception as e:
            note_suppressed('_secure_cleanup/outer', e)
            return None

    def is_using_dopa_model(self):
        """\n        检查当前是否使用ZTX模型（包括ZTX的TRT版本）\n        注意：背闪功能只对ZTX模型有效\n        \n        Returns:\n            bool: 如果当前使用ZTX模型返回True，否则返回False\n        """
        try:
            if not hasattr(self, 'group') or not self.group:
                return False
            if self.group not in self.config.get('groups', {}):
                return False
            current_model = self.config['groups'][self.group].get('infer_model', '')
            original_model = self.config['groups'][self.group].get('original_infer_model', '')
            is_dopa_original = current_model.endswith('.ZTX') or original_model.endswith('.ZTX')
            is_dopa_trt = False
            if current_model.endswith('.engine'):
                if original_model.endswith('ZTX'):
                    is_dopa_trt = True
                elif 'ZTX' in current_model.lower():
                    is_dopa_trt = True
            if is_dopa_original and self.decrypted_model_data is not None:
                return True
            if is_dopa_trt:
                return True
            return False
        except Exception as e:
            return False

    def is_using_encrypted_model(self):
        """\n        检查当前是否使用加密模型（包括ZTX和ZTX模型）\n        \n        Returns:\n            bool: 如果当前使用加密模型返回True，否则返回False\n        """
        try:
            if not hasattr(self, 'group') or not self.group:
                return False
            if self.group not in self.config.get('groups', {}):
                return False
            current_model = self.config['groups'][self.group].get('infer_model', '')
            original_model = self.config['groups'][self.group].get('original_infer_model', '')
            is_encrypted_original = current_model.endswith('.ZTX') or original_model.endswith('.ZTX')
            is_encrypted_trt = False
            if current_model.endswith('.engine'):
                if original_model.endswith('.ZTX'):
                    is_encrypted_trt = True
                elif 'ztx' in current_model.lower():
                    is_encrypted_trt = True
            if is_encrypted_original and self.decrypted_model_data is not None:
                return True
            if is_encrypted_trt:
                return True
            return False
        except Exception as e:
            print(f'检查加密模型状态时出错: {e}')
            return False
