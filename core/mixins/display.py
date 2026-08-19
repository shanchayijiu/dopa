# -*- coding: utf-8 -*-
"""显示与 DPI 工具 Mixin — 从 core.py 提取的对外显示辅助方法。

包含系统 DPI 缩放探测、DPI 感知屏幕尺寸、下拉框刷新（分组/目标参考类别）、
颜色渐变计算。这些方法被 core_gui/core_infercfg/core_keybind/core_aimcfg
以及 Valorant.__init__ 通过 self.* 调用，经 mix-in 继承可达。

依赖 Valorant 提供:
  self.target_reference_class_combo / self.pressed_key_config / self.config
  self.group / self.select_key
  self.render_group_combo()（core_keybind）/ self.get_current_class_num()（core_infercfg）
"""
import ctypes

import win32api


class DisplayMixin:
    """显示与 DPI 工具 Mixin。"""

    def get_system_dpi_scale(self):
        """获取系统DPI缩放比例"""
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
            hdc = ctypes.windll.user32.GetDC(0)
            dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)
            ctypes.windll.user32.ReleaseDC(0, hdc)
            scale = dpi / 96.0
            scale = max(1.0, min(scale, 3.0))
            return scale
        except Exception as e:
            print(f'获取DPI缩放失败，使用默认缩放: {e}')
            return 1.0

    def get_dpi_aware_screen_size(self):
        """获取DPI感知的实际可用屏幕尺寸"""
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            width = root.winfo_screenwidth()
            height = root.winfo_screenheight()
            root.destroy()
            return (width, height)
        except Exception as e:
            width = win32api.GetSystemMetrics(0)
            height = win32api.GetSystemMetrics(1)
            return (width, height)

    def update_combo_methods(self):
        self.render_group_combo()
        self.update_target_reference_class_combo()

    def update_target_reference_class_combo(self):
        """更新目标参考类别下拉框选项"""
        if not hasattr(self, 'target_reference_class_combo') or self.target_reference_class_combo is None:
            return None
        try:
            class_num = self.get_current_class_num()
            items = [f'类别{i}' for i in range(class_num)]
            import dearpygui.dearpygui as dpg
            dpg.configure_item(self.target_reference_class_combo, items=items)
            current_reference_class = self.pressed_key_config.get('target_reference_class', 0)
            if current_reference_class < 0 or current_reference_class >= class_num:
                current_reference_class = 0
                self.config['groups'][self.group]['aim_keys'][self.select_key]['target_reference_class'] = 0
            dpg.set_value(self.target_reference_class_combo, f'类别{current_reference_class}')
        except Exception as e:
            print(f'更新目标参考类别下拉框失败: {e}')

    def get_gradient_color(base_color, step):
        """ 根据基色生成颜色渐变 """
        r, g, b, a = base_color
        factor = 1 + step
        r = min(int(r * factor), 255)
        g = min(int(g * factor), 255)
        b = min(int(b * factor), 255)
        return (r, g, b, a)
